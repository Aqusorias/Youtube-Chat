import concurrent.futures
import time
import sys
from colorama import Fore, Back, Style, init        # colouring in the console
import keyboard         # killswitch
import YoutubeChat

# Replace this with your Youtube's Channel ID
# Find this by going to the Home page of your Youtube Channel and looking at the URL:
# https://www.youtube.com/channel/UCu50dqKnCp06ZsEXrVndWQg -> Channel ID is "UCu50dqKnCp06ZsEXrVndWQg"
# https://www.youtube.com/@LofiGirl -> Channel ID is "@LofiGirl"

# CURRENTLY NOT WORKING, JUST LEAVE IT EMPTY; NOBODY CARES
YOUTUBE_CHANNEL_ID = ""


# Normally if you have the YOUTUBE_CHANNEL_ID you could just have it as "None", but that's bugged currently.
# So just put in the Streams URL in quotes.
# If it's not bugged, only put in the stream Link, if you test it as a unlisted stream.
YOUTUBE_STREAM_URL = 'https://www.youtube.com/watch?v=S1wxVGsdmcw'


# The lower the message, the faster the messages are processed: it's the number of seconds it will take to handle all messages in the queue.
# Twitch delivers messages in batches, if set to 0 it will process it instantly, that's pretty bad if you have many messages incoming.
# So if you don't have many messages, just leave it on 0.2.
MESSAGE_RATE = 0.2

# If you have a lot of messages, you can for example put in 10, so it will only process the first 10 messages of the queue/batch, the rest will be deleted.
# This won't be a problem if you aren't getting a lot of messages, so just leave it on 50.  Not recommended to set higher than 50.
MAX_QUEUE_LENGTH = 50

# Maximum number of messages it will process at the same time, just leave it on 100.
MAX_WORKERS = 100



last_time = time.time()
message_queue = []
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
active_tasks = []
init(autoreset=True)

# Countdown before the script starts, upper the counter if you need to select a window before the program starts.
countdown = 2
print(' ')
if countdown != 0:
    print('Starting countdown ...')
    while countdown > 0:
        print(countdown)
        countdown -= 1
        time.sleep(1)
    print(' ')
    

t = YoutubeChat.YouTube()
t.youtube_connect(YOUTUBE_CHANNEL_ID, YOUTUBE_STREAM_URL)

# Read README.md for more information about the messages / usernames.

# Remember that the Username isn't lowercase.
# If you want to do something with the Username, use for .strip() to remove (?, ., ,, :, ;) and make it lowercase.
def handle_message(message):
    try:
        msg = message['message']
        username = message['username']

        print(f'{username}: {msg}')
            

########################################## Add Rules ##########################################




        # If you use msg.lower(), it will ignore the case of the message.

        # If the message is exactly "hello"
        if msg.strip() == "hello":
            print(Fore.MAGENTA + "User said Hello")

        # If message contains the word "hello"
        if "hello" in msg.strip():
            print(Fore.MAGENTA + "User said Hello")




########################################## <- Love you :3 -> ##########################################
    except Exception as exception:
        print(Fore.RED + "Encountered exception: " + Fore.YELLOW + str(exception))


while True:

    active_tasks = [t for t in active_tasks if not t.done()]

    # Check for new messages
    new_messages = t.receive_messages();
    if new_messages:
        message_queue += new_messages; # New messages are added to the back of the queue
        message_queue = message_queue[-MAX_QUEUE_LENGTH:] # Shorten the queue to only the most recent X messages

    messages_to_handle = []
    if not message_queue: # No messages in the queue
        last_time = time.time()
    else:
        # Determine how many messages it should handle now
        r = 1 if MESSAGE_RATE == 0 else (time.time() - last_time) / MESSAGE_RATE
        n = int(r * len(message_queue))
        if n > 0:
            # Removes the messages from the queue that it handled
            messages_to_handle = message_queue[0:n]
            del message_queue[0:n]
            last_time = time.time();


    # If User presses Shift+Backspace, automatically end the program - Killswitch
    if keyboard.is_pressed('shift+backspace'):
        print(' ')
        print('\033[1m' + Back.YELLOW + Fore.RED + 'Program ended by user' + '\033[0m')
        print(' ')
        exit()
        

    if not messages_to_handle:
        continue
    else:
        for message in messages_to_handle:
            if len(active_tasks) <= MAX_WORKERS:
                active_tasks.append(thread_pool.submit(handle_message, message))
            else:
                print(Back.YELLOW + Fore.RED + Style.BRIGHT + f'WARNING: active tasks ({len(active_tasks)}) exceeds number of workers ({MAX_WORKERS}). ({len(message_queue)} messages in the queue)')