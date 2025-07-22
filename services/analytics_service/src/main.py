from fastapi import FastAPI

app = FastAPI()  # This is what Uvicorn needs to run


@app.get("/")
def read_root():
    return {"message": "Hello from Analytics Service!"}


def main():
    print("Hello from Analytics Service!")


if __name__ == "__main__":
    main()
