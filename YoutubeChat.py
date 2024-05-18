import requests
import re
import time
import json
import concurrent.futures
import traceback

class YouTube:
    session = None
    config = {}
    payload = {}

    thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fetch_job = None
    next_fetch_time = 0

    re_initial_data = re.compile('(?:window\\s*\\[\\s*[\\"\']ytInitialData[\\"\']\\s*\\]|ytInitialData)\\s*=\\s*({.+?})\\s*;')
    re_config = re.compile('(?:ytcfg\\s*.set)\\(({.+?})\\)\\s*;')

    def get_continuation_token(self, data):
        cont = data['continuationContents']['liveChatContinuation']['continuations'][0]
        if 'timedContinuationData' in cont:
            return cont['timedContinuationData']['continuation']
        else:
            return cont['invalidationContinuationData']['continuation']

    def reconnect(self, delay):
        if self.fetch_job and self.fetch_job.running():
            if not self.fetch_job.cancel():
                print("Waiting for fetch job to finish...")
                self.fetch_job.result()
        print(f"Retrying in {delay}...")
        if self.session: self.session.close()
        self.session = None
        self.config = {}
        self.payload = {}
        self.fetch_job = None
        self.next_fetch_time = 0
        time.sleep(delay)
        self.youtube_connect(self.channel_id, self.stream_url)

    def youtube_connect(self, channel_id, stream_url=None):
        print("Connecting to YouTube...")

        self.channel_id = channel_id
        self.stream_url = stream_url

        # Create http client session
        self.session = requests.Session()
        # Spoof user agent so yt thinks we're an upstanding browser
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'
        # Add consent cookie to bypass google's consent page
        requests.utils.add_dict_to_cookiejar(self.session.cookies, {'CONSENT': 'YES+'})

        # Connect using stream_url if provided, otherwise use the channel_id
        if stream_url is not None:
            live_url = self.stream_url
        else:
            live_url = f"https://www.youtube.com/{self.channel_id}/live"
            time.sleep(2)

        res = self.session.get(live_url)
        if res.status_code == 404:
            live_url = f"https://www.youtube.com/{self.channel_id}/live"
            res = self.session.get(live_url)
        if not res.ok:
            if stream_url is not None:
                print(f"Couldn't load the stream URL ({res.status_code} {res.reason}). Is the stream URL correct? {self.stream_url}")
            else:
                print(f"Couldn't load livestream page ({res.status_code} {res.reason}). Is the channel ID correct? {self.channel_id}")
            time.sleep(5)
            exit(1)
        livestream_page = res.text

        # Find initial data in livestream page
        matches = list(self.re_initial_data.finditer(livestream_page))
        if len(matches) == 0:
            print("Couldn't find initial data in livestream page")
            time.sleep(5)
            exit(1)
        initial_data = json.loads(matches[0].group(1))


        # Get continuation token for live chat iframe
        iframe_continuation = None
        try:
            iframe_continuation = initial_data['contents']['twoColumnWatchNextResults']['conversationBar']['liveChatRenderer']['header']['liveChatHeaderRenderer']['viewSelector']['sortFilterSubMenuRenderer']['subMenuItems'][1]['continuation']['reloadContinuationData']['continuation']
        except Exception as e:
            print(f"Couldn't find the livestream chat. Is the channel not live? url: {live_url}")
            time.sleep(5)
            exit(1)

        # Fetch live chat page
        res = self.session.get(f'https://youtube.com/live_chat?continuation={iframe_continuation}')
        if not res.ok:
            print(f"Couldn't load live chat page ({res.status_code} {res.reason})")
            time.sleep(5)
            exit(1)
        live_chat_page = res.text

        # Find initial data in live chat page
        matches = list(self.re_initial_data.finditer(live_chat_page))
        if len(matches) == 0:
            print("Couldn't find initial data in live chat page")
            time.sleep(5)
            exit(1)
        initial_data = json.loads(matches[0].group(1))

        # Find config data
        matches = list(self.re_config.finditer(live_chat_page))
        if len(matches) == 0:
            print("Couldn't find config data in live chat page")
            time.sleep(5)
            exit(1)
        self.config = json.loads(matches[0].group(1))

        # Create payload object for making live chat requests
        token = self.get_continuation_token(initial_data)
        self.payload = {
            "context": self.config['INNERTUBE_CONTEXT'],
            "continuation": token,
            "webClientInfo": {
                "isDocumentHidden": False
            },
        }
        print("Connected.")

    def fetch_messages(self):
        payload_bytes = bytes(json.dumps(self.payload), "utf8")
        res = self.session.post(f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={self.config['INNERTUBE_API_KEY']}&prettyPrint=false", payload_bytes)
        if not res.ok:
            print(f"Failed to fetch messages. {res.status_code} {res.reason}")
            print("Body:", res.text)
            print("Payload:", payload_bytes)
            self.session.close()
            self.session = None
            return []
        try:
            data = json.loads(res.text)
            self.payload['continuation'] = self.get_continuation_token(data)
            cont = data['continuationContents']['liveChatContinuation']
            messages = []
            if 'actions' in cont:
                for action in cont['actions']:
                    if 'addChatItemAction' in action:
                        if 'item' in action['addChatItemAction']:
                            if 'liveChatTextMessageRenderer' in action['addChatItemAction']['item']:
                                item = action['addChatItemAction']['item']['liveChatTextMessageRenderer']
                                messages.append({
                                    'author': item['authorName']['simpleText'],
                                    'content': item['message']['runs']
                                })
            return messages
        except Exception as e:
            print(f"Failed to parse messages.")
            print("Body:", res.text)
            traceback.print_exc()
        return []

    def receive_messages(self):
        if self.session == None:
            self.reconnect(0)
        messages = []
        if not self.fetch_job:
            time.sleep(1.0/60.0)
            if time.time() > self.next_fetch_time:
                self.fetch_job = self.thread_pool.submit(self.fetch_messages)
        else:
            res = []
            timed_out = False
            try:
                res = self.fetch_job.result(1.0/60.0)
            except concurrent.futures.TimeoutError:
                timed_out = True
            except Exception:
                traceback.print_exc()
                self.session.close()
                self.session = None
                return
            if not timed_out:
                self.fetch_job = None
                self.next_fetch_time = time.time() + 10
            for item in res:
                msg = {
                    'username': item['author'],
                    'message': ''
                }
                for part in item['content']:
                    if 'text' in part:
                        msg['message'] += part['text']
                    elif 'emoji' in part:
                        msg['message'] += part['emoji']['emojiId']
                messages.append(msg)
        return messages