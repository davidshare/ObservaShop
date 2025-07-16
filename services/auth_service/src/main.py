from fastapi import FastAPI

app = FastAPI()  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from auth-service!"}


def main():
    print("Hello from auth-service!")


if __name__ == "__main__":
    main()
