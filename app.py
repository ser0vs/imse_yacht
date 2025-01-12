from flask import Flask, render_template, request, redirect, flash, url_for


import subprocess, os, mysql.connector
from datetime import datetime


app = Flask(__name__)
app.secret_key = "secret_key_for_flask_flash"


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


@app.route("/place_order_form", methods=["GET"])
def place_order_form():
    return render_template("place_order.html")


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


@app.route("/orders_summary", methods=["GET", "POST"])
def orders_summary():
    """Displays a form for filtering orders by date range and shows results."""
    filtered_orders = []
    error_message = None

    if request.method == "POST":
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

        # Basic validation
        if not start_date or not end_date:
            error_message = "Both start date and end date are required."
        else:
            try:
                connection = connect_to_database()
                cursor = connection.cursor(dictionary=True)

                # Construct and execute the SQL query
                sql_query = """
                SELECT
                    co.orderID,
                    c.customerID,
                    c.name AS customerName,
                    y.yachtID,
                    y.model AS yachtModel,
                    e.employeeID,
                    e.name AS builderName,
                    b.specialization AS builderSpecialization
                FROM
                    CustomerOrder co
                    JOIN Customer c ON co.customerID = c.customerID
                    JOIN Yacht y ON y.orderID = co.orderID
                    LEFT JOIN CustomerOrderBuilder cob ON cob.orderID = co.orderID
                    LEFT JOIN Builder b ON cob.employeeID = b.employeeID
                    LEFT JOIN Employee e ON b.employeeID = e.employeeID
                WHERE
                    co.dateOfCreation BETWEEN %s AND %s
                """

                cursor.execute(sql_query, (start_date, end_date))
                filtered_orders = cursor.fetchall()

            except Exception as e:
                error_message = f"An error occurred while fetching data: {e}"
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()

    return render_template(
        "orders_summary.html",
        filtered_orders=filtered_orders,
        error_message=error_message,
    )


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
        cursor.execute(
            """
            SELECT co.orderID, co.dateOfCreation, co.price, GROUP_CONCAT(b.employeeID) AS builderIDs
            FROM CustomerOrder co
            LEFT JOIN CustomerOrderBuilder cob ON co.orderID = cob.orderID
            LEFT JOIN Builder b ON cob.employeeID = b.employeeID
            GROUP BY co.orderID;
        """
        )
        orders = cursor.fetchall()

        # Fetch all Employees
        cursor.execute(
            """
            SELECT e.employeeID, e.name, e.email,
                   CASE WHEN b.employeeID IS NOT NULL THEN 'Yes' ELSE 'No' END AS isBuilder,
                   b.role, b.specialization
            FROM Employee e
            LEFT JOIN Builder b ON e.employeeID = b.employeeID;
        """
        )
        employees = cursor.fetchall()

        if request.method == "POST":
            order_id = request.form.get("orderID")
            employee_id = request.form.get("employeeID")

            # Validate input
            if not order_id or not employee_id:
                error_message = "Both Order ID and Employee ID are required."
            else:
                # Check if Order and Employee exist
                cursor.execute(
                    "SELECT * FROM CustomerOrder WHERE orderID = %s", (order_id,)
                )
                order = cursor.fetchone()
                cursor.execute(
                    "SELECT e.*, b.employeeID AS isBuilder FROM Employee e LEFT JOIN Builder b ON e.employeeID = b.employeeID WHERE e.employeeID = %s",
                    (employee_id,),
                )
                employee = cursor.fetchone()

                if not order:
                    error_message = "Order ID does not exist."
                elif not employee:
                    error_message = "Employee ID does not exist."
                elif not employee["isBuilder"]:
                    error_message = "The chosen employee is not a builder."
                else:
                    # Check if the order is already assigned to the employee
                    cursor.execute(
                        """
                        SELECT * FROM CustomerOrderBuilder
                        WHERE orderID = %s AND employeeID = %s
                    """,
                        (order_id, employee_id),
                    )
                    assignment = cursor.fetchone()

                    if assignment:
                        error_message = (
                            "This order is already assigned to the chosen employee."
                        )
                    else:
                        # Assign the Order to the Builder
                        cursor.execute(
                            """
                            INSERT INTO CustomerOrderBuilder (orderID, employeeID)
                            VALUES (%s, %s)
                        """,
                            (order_id, employee_id),
                        )
                        connection.commit()
                        success_message = "Order successfully assigned to the employee."

    except Exception as e:
        error_message = f"An error occurred: {e}"

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "usecase_student2.html",
        orders=orders,
        employees=employees,
        error_message=error_message,
        success_message=success_message,
    )

@app.route("/report_student2", methods=["GET", "POST"])
def report_student2():
    connection = None
    cursor = None
    builders = []
    specialization = ""

    try:
        if request.method == "POST":
            # Get specialization from the form
            specialization = request.form.get("specialization", "").strip()

        connection = connect_to_database()
        cursor = connection.cursor(dictionary=True)

        # Build SQL query with optional specialization filter
        if specialization:
            query = """
                SELECT 
                    b.specialization AS builderSpecialization,    
                    e.employeeID,
                    e.name AS builderName,
                    b.role AS builderRole,
                    y.yachtID,
                    y.model AS yachtModel,
                    y.length AS yachtLength
                FROM 
                    Builder b
                JOIN 
                    Employee e ON b.employeeID = e.employeeID
                JOIN 
                    CustomerOrderBuilder cob ON b.employeeID = cob.employeeID
                JOIN 
                    CustomerOrder co ON cob.orderID = co.orderID
                JOIN 
                    Yacht y ON co.orderID = y.orderID
                WHERE 
                    b.specialization = %s
                ORDER BY 
                    e.employeeID, b.role ASC, e.name ASC
            """
            cursor.execute(query, (specialization,))
        else:
            query = """
                SELECT 
                    b.specialization AS builderSpecialization,    
                    e.employeeID,
                    e.name AS builderName,
                    b.role AS builderRole,
                    y.yachtID,
                    y.model AS yachtModel,
                    y.length AS yachtLength
                FROM 
                    Builder b
                JOIN 
                    Employee e ON b.employeeID = e.employeeID
                JOIN 
                    CustomerOrderBuilder cob ON b.employeeID = cob.employeeID
                JOIN 
                    CustomerOrder co ON cob.orderID = co.orderID
                JOIN 
                    Yacht y ON co.orderID = y.orderID
                ORDER BY 
                    e.employeeID, b.role ASC, e.name ASC
            """
            cursor.execute(query)

        builders = cursor.fetchall()

    except Exception as e:
        return f"An error occurred: {e}"
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template("report_student2.html", builders=builders)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
