from fastapi import FastAPI

app = FastAPI()  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from Product Service!"}


def main():
    print("Hello from Product Service!")


if __name__ == "__main__":
    main()
