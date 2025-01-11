from flask import Flask, render_template, redirect, url_for, request
import subprocess, os, mysql.connector
from datetime import datetime



app = Flask(__name__)


# Database connection function
def connect_to_database():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpassword"),
        database=os.getenv("DB_NAME", "yacht_building"),
        port=int(os.getenv("DB_PORT", 3306)),
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/place_order", methods=["POST"])
def place_order():
    connection = None
    cursor = None
    try:
        # Get data from the form
        customer_name = request.form.get("name")
        customer_email = request.form.get("email")
        yacht_model = request.form.get("model")
        yacht_length = int(request.form.get("length"))

        # Connect to the database
        connection = connect_to_database()
        cursor = connection.cursor()

        # Check if the customer already exists by email
        cursor.execute(
            "SELECT customerID FROM Customer WHERE email = %s", (customer_email,)
        )
        result = cursor.fetchone()

        if result:
            # Customer exists, reuse the ID
            customer_id = result[0]
        else:
            # Customer doesn't exist, create a new one
            cursor.execute(
                "INSERT INTO Customer (name, email) VALUES (%s, %s)",
                (customer_name, customer_email),
            )
            customer_id = cursor.lastrowid

        # Create a new CustomerOrder
        date_of_creation = datetime.now().strftime("%Y-%m-%d")  # Use current date
        price = yacht_length * 1000  # Example pricing logic: $1000 per meter
        cursor.execute(
            "INSERT INTO CustomerOrder (dateOfCreation, price, customerID) VALUES (%s, %s, %s)",
            (date_of_creation, price, customer_id),
        )
        order_id = cursor.lastrowid

        # Create a new Yacht linked to the order
        cursor.execute(
            "SELECT IFNULL(MAX(yachtID), 0) + 1 FROM Yacht"
        )  # Generate the next yacht ID
        yacht_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO Yacht (yachtID, orderID, model, length) VALUES (%s, %s, %s, %s)",
            (yacht_id, order_id, yacht_model, yacht_length),
        )

        # Commit the transaction
        connection.commit()

        # Success message
        success_message = f"""
        Order successfully placed!<br>
        Customer: {customer_name} ({customer_email})<br>
        Yacht Model: {yacht_model}<br>
        Yacht Length: {yacht_length} meters<br>
        Total Price: ${price}<br>
        Order ID: {order_id}<br>
        Yacht ID: {yacht_id}
        """
        return success_message
    except Exception as e:
        return f"Error while placing order: {e}"
    finally:
        # Close cursor and connection if they were created
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/import_data", methods=["POST"])
def import_data():
    try:
        subprocess.run(["python3", "db_filling.py"], check=True)
        return "Data import successful!"
    except Exception as e:
        return f"Error during data import: {e}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
