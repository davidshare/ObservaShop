from fastapi import FastAPI

app = FastAPI()  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from Notification Service!"}


def main():
    print("Hello from Notification Service!")


if __name__ == "__main__":
    main()
