from flask import Flask, render_template, request, redirect, flash, url_for
import subprocess
import os
import mysql.connector
import pymongo
from datetime import datetime, date, time

app = Flask(__name__)
app.secret_key = "secret_key_for_flask_flash"


# Connect to MySQL
def connect_to_database():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpassword"),
        database=os.getenv("DB_NAME", "yacht_building"),
        port=int(os.getenv("DB_PORT", 3306)),
    )


# Connect to MongoDB (use environment variables for host, port, db name)
def connect_to_mongo():
    host = os.getenv("MONGO_HOST", "mongodb")
    port = os.getenv("MONGO_PORT", "27017")
    db_name = os.getenv("MONGO_DB", "yacht_building_nosql")

    mongo_client = pymongo.MongoClient(f"mongodb://{host}:{port}/")
    return mongo_client[db_name]


# Data Migration Function
@app.route("/migrate_data", methods=["POST"])
def migrate_data():
    try:
        # Connect to SQL and MongoDB
        sql_connection = connect_to_database()
        mongo_db = connect_to_mongo()

        # MongoDB collections
        orders_collection = mongo_db["orders"]
        employees_collection = mongo_db["employees"]

        # Clear existing data in MongoDB
        orders_collection.delete_many({})
        employees_collection.delete_many({})

        cursor = sql_connection.cursor(dictionary=True)

        # Migrate Orders Collection
        cursor.execute(
            """
            SELECT o.orderID, o.dateOfCreation, o.price,
                   c.customerID, c.name AS customerName, c.email AS customerEmail
            FROM CustomerOrder o
            JOIN Customer c ON o.customerID = c.customerID
            """
        )
        orders = cursor.fetchall()

        cursor.execute("SELECT * FROM Yacht")
        yachts = cursor.fetchall()

        cursor.execute(
            """
            SELECT e.employeeID, e.name, e.email,
                   b.role, b.specialization, cob.orderID
            FROM Employee e
            LEFT JOIN Builder b ON e.employeeID = b.employeeID
            LEFT JOIN CustomerOrderBuilder cob ON e.employeeID = cob.employeeID
            """
        )
        builders = cursor.fetchall()

        for order in orders:
            # Get yachts associated with this order
            order_yachts = [
                {
                    "yachtID": yacht["yachtID"],
                    "model": yacht["model"],
                    "length": yacht["length"],
                }
                for yacht in yachts
                if yacht["orderID"] == order["orderID"]
            ]

            # Get builders associated with this order
            assigned_builders = [
                {
                    "employeeID": builder["employeeID"],
                    "name": builder["name"],
                    "email": builder["email"],
                    "role": builder["role"],
                    "specialization": builder["specialization"],
                }
                for builder in builders
                if builder["orderID"] == order["orderID"]
            ]

            # Handle 'dateOfCreation' properly for MongoDB.
            # If 'order["dateOfCreation"]' is a date or datetime, PyMongo can't encode a plain date.
            # Convert it to datetime at midnight:
            date_field = order["dateOfCreation"]
            if isinstance(date_field, date) and not isinstance(date_field, datetime):
                date_field = datetime.combine(date_field, time.min)

            # Insert order document into MongoDB
            orders_collection.insert_one(
                {
                    "orderID": order["orderID"],
                    "dateOfCreation": date_field,
                    "price": order["price"],
                    "customer": {
                        "customerID": order["customerID"],
                        "name": order["customerName"],
                        "email": order["customerEmail"],
                    },
                    "yachts": order_yachts,
                    "assignedBuilders": assigned_builders,
                }
            )

        # Migrate Employees Collection
        cursor.execute("SELECT * FROM Employee")
        employees = cursor.fetchall()

        cursor.execute("SELECT * FROM BuddyOf")
        buddies = cursor.fetchall()

        # Build a list of base employee documents
        employee_docs = [
            {
                "employeeID": emp["employeeID"],
                "name": emp["name"],
                "email": emp["email"],
                "role": None,
                "specialization": None,
            }
            for emp in employees
        ]

        # Add builder details
        for builder in builders:
            for emp in employee_docs:
                if emp["employeeID"] == builder["employeeID"]:
                    emp["role"] = builder["role"]
                    emp["specialization"] = builder["specialization"]

        # Add buddy relationships
        for emp in employee_docs:
            emp["buddies"] = [
                buddy["employeeID2"]
                for buddy in buddies
                if buddy["employeeID1"] == emp["employeeID"]
            ]

        # Insert employee docs into MongoDB
        employees_collection.insert_many(employee_docs)

        cursor.close()
        sql_connection.close()

        return "Data migration completed successfully!"
    except Exception as e:
        return f"Error during data migration: {e}"


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
        price = yacht_length * 1000  # Example pricing logic
        cursor.execute(
            "INSERT INTO CustomerOrder (dateOfCreation, price, customerID) VALUES (%s, %s, %s)",
            (date_of_creation, price, customer_id),
        )
        order_id = cursor.lastrowid

        # Create a new Yacht linked to the order
        cursor.execute("SELECT IFNULL(MAX(yachtID), 0) + 1 FROM Yacht")
        yacht_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO Yacht (yachtID, orderID, model, length) VALUES (%s, %s, %s, %s)",
            (yacht_id, order_id, yacht_model, yacht_length),
        )

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
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/orders_summary", methods=["GET", "POST"])
def orders_summary():
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
            SELECT co.orderID, co.dateOfCreation, co.price,
                   GROUP_CONCAT(b.employeeID) AS builderIDs
            FROM CustomerOrder co
            LEFT JOIN CustomerOrderBuilder cob ON co.orderID = cob.orderID
            LEFT JOIN Builder b ON cob.employeeID = b.employeeID
            GROUP BY co.orderID
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
            LEFT JOIN Builder b ON e.employeeID = b.employeeID
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
                    """
                    SELECT e.*, b.employeeID AS isBuilder
                    FROM Employee e
                    LEFT JOIN Builder b ON e.employeeID = b.employeeID
                    WHERE e.employeeID = %s
                    """,
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


@app.route("/usecase_student2_nosql", methods=["POST"])
def usecase_student2_nosql():
    """
    Assign an existing MongoDB 'orders' doc to a builder by pushing to the 'assignedBuilders' array.
    """
    try:
        db = connect_to_mongo()
        orders_coll = db.orders

        # Example: we get 'orderID' and some builder details from a form
        order_id = int(request.form.get("orderID"))
        employee_id = int(request.form.get("employeeID"))
        builder_name = request.form.get("builderName")
        builder_email = request.form.get("builderEmail")
        builder_role = request.form.get("builderRole")
        builder_spec = request.form.get("builderSpecialization")

        # Perform update in Mongo
        result = orders_coll.update_one(
            {"orderID": order_id},
            {
                "$push": {
                    "assignedBuilders": {
                        "employeeID": employee_id,
                        "name": builder_name,
                        "email": builder_email,
                        "role": builder_role,
                        "specialization": builder_spec
                    }
                }
            }
        )

        if result.modified_count > 0:
            return f"Order {order_id} assigned to {builder_name} (NoSQL)!"
        else:
            return f"Could not find order {order_id} or assignment failed."

    except Exception as e:
        return f"Error in assign_order_nosql: {e}"



@app.route("/report_student2_nosql", methods=["GET", "POST"])
def report_student2_nosql():
    """
    NoSQL-based builder specialization report.
    """
    db = connect_to_mongo()
    orders_coll = db.orders

    builders = []
    error_message = None
    specialization = ""

    if request.method == "POST":
        specialization = request.form.get("specialization", "").strip()
        try:
            pipeline = []

            # If user specified a specialization, match it
            if specialization:
                pipeline.append({
                    "$match": {
                        "assignedBuilders.specialization": specialization
                    }
                })

            # Unwind assignedBuilders to treat each builder as a row
            pipeline.append({"$unwind": "$assignedBuilders"})

            # If we matched above, filter again
            if specialization:
                pipeline.append({
                    "$match": {
                        "assignedBuilders.specialization": specialization
                    }
                })

            pipeline.append({
                "$project": {
                    "_id": 0,
                    "builder.employeeID": "$assignedBuilders.employeeID",
                    "builder.name": "$assignedBuilders.name",
                    "builder.role": "$assignedBuilders.role",
                    "builder.specialization": "$assignedBuilders.specialization",
                    "yachts": 1
                }
            })

            pipeline.append({"$sort": {"builder.employeeID": 1}})

            results = list(orders_coll.aggregate(pipeline))
            builders = results

        except Exception as e:
            error_message = f"Mongo error: {e}"

    return render_template("report_student2_nosql.html",
                           builders=builders,
                           error_message=error_message)




if __name__ == "__main__":
    # Run the Flask app on 0.0.0.0 so Docker can map the port
    app.run(host="0.0.0.0", port=5001, debug=True)
