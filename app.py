from flask import Flask, render_template, redirect, url_for
import subprocess

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/import_data", methods=["POST"])
def import_data():
    try:
        subprocess.run(["python3", "db_filling.py"], check=True)
        return "Data import successful!"
    except Exception as e:
        return f"Error during data import: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
