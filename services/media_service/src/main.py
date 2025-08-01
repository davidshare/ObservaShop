from fastapi import FastAPI

app = FastAPI()  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from Media Service!"}


def main():
    print("Hello from Media Service!")


if __name__ == "__main__":
    main()
