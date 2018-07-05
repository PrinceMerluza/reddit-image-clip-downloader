import praw
import shutil
import requests
import os, io, zipfile, json
from Crypto.Cipher import AES
from pprint import pprint
from urllib.parse import urlparse, urlunparse

reddit = None


def main():
    with open('config.json') as config_f:
        config = json.load(config_f)

    setup_reddit(config['username'], config['password'],
                 config['client_id'], config['client_secret'],
                 config['user_agent'])
    me = reddit.redditor('terminal_styles')
    my_multireddits = me.multireddits()
    key = config['key'].encode('utf-8')

    print("""
        1. Subreddit
        2. Multireddit
        3. Decode files
        """)
    command = input("> ")

    if command == '1':
        subreddit = input("Which subredit? ")
        time_filter = input("time_filter: ") or 'month'
        limit = int(input("limit: ") or 100)
        download_files(subreddit, key, time_filter, limit)

    elif command == '2':
        multireddit = input("Which multireddit? ")
        time_filter = input("time_filter: ") or 'month'
        limit = int(input("limit: ") or 100)

        subreddits = list(filter(lambda mr: mr.name == multireddit, my_multireddits))[0].subreddits
        for subr in subreddits:
            download_files(subr.display_name, key, time_filter, limit)

    elif command == '3':
        files = [f for f in os.listdir('./encrypted/') if os.path.isfile(os.path.join('./encrypted/', f))]
        for file in files:
            decrypt_file('./encrypted/' + file, key)


# Set up the Reddit API
def setup_reddit(username, password, client_id, client_secret, user_agent):
    global reddit

    # PRAW config
    reddit = praw.Reddit(client_id=client_id,
                         client_secret=client_secret,
                         user_agent=user_agent,
                         username=username,
                         password=password)
    print("Succesfully logged in.")


# Download files from a subreddit
def download_files(subreddit_name, key, time_filter='week', limit=100):
    global reddit

    subreddit = reddit.subreddit(subreddit_name)
    image_extensions = ['.jpg', '.png', '.gif', '.jpeg']

    zip_data = io.BytesIO()
    zipf = zipfile.ZipFile(zip_data, 'w', zipfile.ZIP_DEFLATED)

    for submission in subreddit.top(time_filter, limit=limit):
        print('---------------------------')
        print(submission.title)

        extension = ''
        url = submission.url

        parsed_url = urlparse(url)
        url_extension = os.path.splitext(parsed_url.path)[-1]

        filename = os.path.splitext(parsed_url.path.split('/')[-1])[0]

        # Handle general image files
        # Ex: http://website.com/image.png
        if url_extension in image_extensions:
            extension = url_extension

        # Handle Imgur gifv URLs and turn them to mp4
        # http://i.imgur.com/2W3e4R.gifv
        if (parsed_url.netloc == 'i.imgur.com') and (url_extension == '.gifv'):
            extension = '.mp4'

            previous_path, previous_ext = os.path.splitext(parsed_url.path)
            new_path = previous_path + extension

            modified_url = parsed_url._replace(path=new_path)

            url = urlunparse(modified_url)

        # Handle Imgur links that are not direct to the image
        # Ex: http://imgur.com/2W3e4R
        if url_extension == '' and parsed_url.netloc == 'imgur.com':
            modified_url = parsed_url._replace(netloc='i.imgur.com')
            url = urlunparse(modified_url)
            extension = '.jpg'
            url += extension

        if url_extension == '' and parsed_url.netloc == 'gfycat.com':
            modified_url = parsed_url._replace(netloc='giant.gfycat.com')
            url = urlunparse(modified_url)
            extension = '.webm'
            url += extension

        # Only download if we know what type of file we're dealing with
        if extension != '':
            print(url)
            response = requests.get(url, stream=True)

            file_in_memory = io.BytesIO()

            shutil.copyfileobj(response.raw, file_in_memory)
            file_buff = file_in_memory.getbuffer()
            del response

            zipf.writestr(filename + extension, file_buff)

    zipf.close()
    encrypt_file(key, zip_data, subreddit_name + '.' + time_filter)


def encrypt_file(key, file_object, filename):
    cipher = AES.new(key, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(file_object.getvalue())
    file_out = open('./encrypted/' + filename + ".bin", "wb")
    [file_out.write(x) for x in (cipher.nonce, tag, ciphertext)]


def decrypt_file(filename, key):
    file_in = open(filename, "rb")
    nonce, tag, ciphertext = [file_in.read(x) for x in (16, 16, -1)]

    cipher = AES.new(key, AES.MODE_EAX, nonce)
    data = cipher.decrypt_and_verify(ciphertext, tag)

    file_out = open(filename + '.zip', 'wb')
    file_out.write(data)
    file_out.close()

if __name__ == "__main__":
    main()