import os

def check_screenshots():
    folder = r"C:\Users\adars\.gemini\antigravity\brain\810d7329-1d51-457b-8503-cd66d8427658"
    print("Checking for subagent screenshots:")
    for file in os.listdir(folder):
        if "splash" in file and file.endswith(".png"):
            path = os.path.join(folder, file)
            print(f"- {file} ({os.path.getsize(path)} bytes)")

if __name__ == "__main__":
    check_screenshots()
