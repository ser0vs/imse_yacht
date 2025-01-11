from flask import Flask, render_template, request, redirect, flash
import mysql.connector
import os, subprocess

app = Flask(__name__)
app.secret_key = "secret_key_for_flask_flash"

def connect_to_database():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpassword"),
        database=os.getenv("DB_NAME", "yacht_building"),
        port=int(os.getenv("DB_PORT", 3306))
    )

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

@app.route("/usecase_student2", methods=["GET", "POST"])
def update_employee_info():
    connection = connect_to_database()
    cursor = connection.cursor(dictionary=True)
    error_message = ""
    success_message = ""

    try:
        # Fetch Customer Orders with assigned Builders
        cursor.execute("""
            SELECT co.orderID, co.dateOfCreation, co.price, GROUP_CONCAT(b.employeeID) AS builderIDs
            FROM CustomerOrder co
            LEFT JOIN CustomerOrderBuilder cob ON co.orderID = cob.orderID
            LEFT JOIN Builder b ON cob.employeeID = b.employeeID
            GROUP BY co.orderID;
        """)
        orders = cursor.fetchall()

        # Fetch all Employees
        cursor.execute("""
            SELECT e.employeeID, e.name, e.email,
                   CASE WHEN b.employeeID IS NOT NULL THEN 'Yes' ELSE 'No' END AS isBuilder,
                   b.role, b.specialization
            FROM Employee e
            LEFT JOIN Builder b ON e.employeeID = b.employeeID;
        """)
        employees = cursor.fetchall()

        if request.method == "POST":
            order_id = request.form.get("orderID")
            employee_id = request.form.get("employeeID")

            # Validate input
            if not order_id or not employee_id:
                error_message = "Both Order ID and Employee ID are required."
            else:
                # Check if Order and Employee exist
                cursor.execute("SELECT * FROM CustomerOrder WHERE orderID = %s", (order_id,))
                order = cursor.fetchone()
                cursor.execute("SELECT e.*, b.employeeID AS isBuilder FROM Employee e LEFT JOIN Builder b ON e.employeeID = b.employeeID WHERE e.employeeID = %s", (employee_id,))
                employee = cursor.fetchone()

                if not order:
                    error_message = "Order ID does not exist."
                elif not employee:
                    error_message = "Employee ID does not exist."
                elif not employee["isBuilder"]:
                    error_message = "The chosen employee is not a builder."
                else:
                    # Check if the order is already assigned to the employee
                    cursor.execute("""
                        SELECT * FROM CustomerOrderBuilder
                        WHERE orderID = %s AND employeeID = %s
                    """, (order_id, employee_id))
                    assignment = cursor.fetchone()

                    if assignment:
                        error_message = "This order is already assigned to the chosen employee."
                    else:
                        # Assign the Order to the Builder
                        cursor.execute("""
                            INSERT INTO CustomerOrderBuilder (orderID, employeeID)
                            VALUES (%s, %s)
                        """, (order_id, employee_id))
                        connection.commit()
                        success_message = "Order successfully assigned to the employee."

    except Exception as e:
        error_message = f"An error occurred: {e}"

    finally:
        cursor.close()
        connection.close()

    return render_template("usecase_student2.html", orders=orders, employees=employees, error_message=error_message, success_message=success_message)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
