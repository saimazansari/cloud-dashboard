from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Cloud Dashboard</h1>
    <p>Welcome Saima!</p>
    <p>Frontend: Python Flask</p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)