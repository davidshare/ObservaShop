from fastapi import FastAPI

app = FastAPI()  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from authz-service!"}


def main():
    print("Hello from authz-service!")


if __name__ == "__main__":
    main()
