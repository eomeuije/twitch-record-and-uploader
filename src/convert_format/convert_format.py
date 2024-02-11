import subprocess
import os
from src.upload.googledrive import Upload

class convert_format:
    def convert_video(input_path, output_path, username: str, gpu: bool = True):
    # GPU를 사용하여 ffmpeg 호출
        if gpu:
            command = [
                'ffmpeg',
                '-hwaccel', 'cuda',  # CUDA를 사용한 GPU 가속
                '-i', input_path,    # 입력 TS 파일
                '-c:v', 'h264_nvenc',  # NVIDIA GPU를 사용한 H.264 인코딩
                '-c:a', 'aac',       # AAC 오디오 코덱
                output_path           # 출력 MP4 파일
            ]
        else:
            command = [
                'ffmpeg',
                '-i', input_path,    # 입력 TS 파일
                '-c:a', 'aac',       # AAC 오디오 코덱
                output_path           # 출력 MP4 파일
            ]

        subprocess.run(command)
        os.remove(input_path)
        if username != None:
            Upload.upload(username)

if __name__ == "__main__":
    ts_file_path = "input.ts"
    mp4_file_path = "output.mp4"

    convert_format.convert_video(ts_file_path, mp4_file_path, None)