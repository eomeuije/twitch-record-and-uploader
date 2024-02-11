import argparse
import threading
from src.upload.googledrive import Upload
from src.twitch_recorder_direct import TwitchRecorder
from src.convert_format.convert_format import convert_format

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Simple Twitch recording script")
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-q", "--quality", default="best")
    parser.add_argument("-c", "--country", default="JAPAN")
    parser.add_argument("-d", "--drive", default="True")
    parser.add_argument("-f", "--ffmpeg", default="True")
    parser.add_argument("-g", "--gpu", default="True")
    # parser.add_argument("--logging-telegram", action="store_true")
    args = parser.parse_args()

    #logger.setLevel(logging.DEBUG)
    if args.drive.lower() == 'true':
        u = Upload()
        thread = threading.Thread(target=u.upload, args=[args.username])
        thread.start()

    recorder = TwitchRecorder(args.username, args.country,  args.quality, args.drive.lower() == 'true', args.ffmpeg.lower() == 'true', args.gpu.lower() == 'true')
    recorder.run()