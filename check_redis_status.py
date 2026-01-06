import socket

def check_redis(host='localhost', port=6379):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex((host, port))
        s.close()
        
        if result == 0:
            print(f"SUCCESS: Redis is reachable at {host}:{port}")
            return True
        else:
            print(f"FAILURE: Redis is NOT reachable at {host}:{port}. Error code: {result}")
            return False
    except Exception as e:
        print(f"ERROR: Exception while checking Redis: {e}")
        return False

if __name__ == "__main__":
    check_redis()