from flask import Flask, render_template, request, redirect, flash, url_for
import subprocess
import os, json
import mysql.connector
import pymongo
from datetime import datetime, date, time

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



def connect_to_mongo():
    host = os.getenv("MONGO_HOST", "mongodb")
    port = os.getenv("MONGO_PORT", "27017")
    db_name = os.getenv("MONGO_DB", "yacht_building_nosql")

    mongo_client = pymongo.MongoClient(f"mongodb://{host}:{port}/")
    return mongo_client[db_name]


@app.route("/place_order_form_nosql", methods=["GET"])
def place_order_form_nosql():
    return render_template("place_order_nosql.html")


@app.route("/place_order_nosql", methods=["POST"])
def place_order_nosql():
    try:
        customer_name = request.form.get("name")
        customer_email = request.form.get("email")
        yacht_model = request.form.get("model")
        yacht_length = int(request.form.get("length"))

        mongo_db = connect_to_mongo()
        orders_collection = mongo_db["orders"]

        existing_customer = orders_collection.find_one(
            {"customer.email": customer_email}
        )

        if existing_customer:
            customer_id = existing_customer["customer"]["customerID"]
        else:
            customer_id = orders_collection.estimated_document_count() + 1

        order_id = orders_collection.estimated_document_count() + 1

        orders_collection.insert_one(
            {
                "orderID": order_id,
                "dateOfCreation": datetime.now(),
                "price": yacht_length * 1000,
                "customer": {
                    "customerID": customer_id,
                    "name": customer_name,
                    "email": customer_email,
                },
                "yacht": {
                    "model": yacht_model,
                    "length": yacht_length,
                },
            }
        )

        success_message = f"""
        Order successfully placed!<br>
        Customer: {customer_name} ({customer_email})<br>
        Yacht Model: {yacht_model}<br>
        Yacht Length: {yacht_length} meters<br>
        Total Price: ${yacht_length * 1000}<br>
        Order ID: {order_id}<br>
        """
        return success_message
    except Exception as e:
        return f"Error while placing order (NoSQL): {e}"


@app.route("/migrate_data", methods=["POST"])
def migrate_data():
    try:
        sql_connection = connect_to_database()
        mongo_db = connect_to_mongo()

        orders_collection = mongo_db["orders"]
        employees_collection = mongo_db["employees"]

        orders_collection.delete_many({})
        employees_collection.delete_many({})

        cursor = sql_connection.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Employee")
        employees = cursor.fetchall()

        cursor.execute(
            """
            SELECT e.employeeID, b.role, b.specialization
            FROM Employee e
            INNER JOIN Builder b ON e.employeeID = b.employeeID
            """
        )
        builders = {b["employeeID"]: b for b in cursor.fetchall()}

        cursor.execute("SELECT * FROM BuddyOf")
        buddies = cursor.fetchall()

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

        cursor.execute("SELECT * FROM CustomerOrderBuilder")
        order_builder_assignments = cursor.fetchall()

        migrated_employees = []
        migrated_orders = []

        for emp in employees:
            emp_doc = {
                "employeeID": emp["employeeID"],
                "name": emp["name"],
                "email": emp["email"],
                "isBuilder": emp["employeeID"] in builders,
                "role": builders.get(emp["employeeID"], {}).get("role"),
                "specialization": builders.get(emp["employeeID"], {}).get("specialization"),
                "buddies": [
                    buddy["employeeID2"]
                    for buddy in buddies
                    if buddy["employeeID1"] == emp["employeeID"]
                ],
            }
            migrated_employees.append(emp_doc)

        for order in orders:
            order_yachts = [
                {
                    "yachtID": yacht["yachtID"],
                    "model": yacht["model"],
                    "length": yacht["length"],
                }
                for yacht in yachts
                if yacht["orderID"] == order["orderID"]
            ]

            assigned_builders = [
                {
                    "employeeID": assignment["employeeID"],
                    "name": next(
                        (emp["name"] for emp in employees if emp["employeeID"] == assignment["employeeID"]),
                        None
                    ),
                    "email": next(
                        (emp["email"] for emp in employees if emp["employeeID"] == assignment["employeeID"]),
                        None
                    ),
                    "role": builders.get(assignment["employeeID"], {}).get("role"),
                    "specialization": builders.get(assignment["employeeID"], {}).get("specialization"),
                }
                for assignment in order_builder_assignments
                if assignment["orderID"] == order["orderID"]
            ]

            date_field = order["dateOfCreation"]
            if isinstance(date_field, date) and not isinstance(date_field, datetime):
                date_field = datetime.combine(date_field, time.min)

            order_doc = {
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

            migrated_orders.append(order_doc)

        employees_collection.insert_many(migrated_employees)
        orders_collection.insert_many(migrated_orders)

        debug_data = {
            "employees": migrated_employees,
            "orders": migrated_orders
        }

        return f"Data successfully migrated!"

    except Exception as e:
        return f"Error during data migration: {e}"


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/index_nosql", methods=["GET"])
def nosql_page():
    return render_template("index_nosql.html")


@app.route("/place_order_form", methods=["GET"])
def place_order_form():
    return render_template("place_order.html")


@app.route("/place_order", methods=["POST"])
def place_order():
    connection = None
    cursor = None
    try:
        customer_name = request.form.get("name")
        customer_email = request.form.get("email")
        yacht_model = request.form.get("model")
        yacht_length = int(request.form.get("length"))

        connection = connect_to_database()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT customerID FROM Customer WHERE email = %s", (customer_email,)
        )
        result = cursor.fetchone()

        if result:
            customer_id = result[0]
        else:
            cursor.execute(
                "INSERT INTO Customer (name, email) VALUES (%s, %s)",
                (customer_name, customer_email),
            )
            customer_id = cursor.lastrowid

        date_of_creation = datetime.now().strftime("%Y-%m-%d")
        price = yacht_length * 1000
        cursor.execute(
            "INSERT INTO CustomerOrder (dateOfCreation, price, customerID) VALUES (%s, %s, %s)",
            (date_of_creation, price, customer_id),
        )
        order_id = cursor.lastrowid

        cursor.execute("SELECT IFNULL(MAX(yachtID), 0) + 1 FROM Yacht")
        yacht_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO Yacht (yachtID, orderID, model, length) VALUES (%s, %s, %s, %s)",
            (yacht_id, order_id, yacht_model, yacht_length),
        )

        connection.commit()

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


@app.route("/orders_summary_nosql", methods=["GET", "POST"])
def orders_summary_nosql():
    filtered_orders = []
    error_message = None

    try:
        mongo_db = connect_to_mongo()
        orders_collection = mongo_db["orders"]

        if request.method == "POST":
            start_date = request.form.get("start_date")
            end_date = request.form.get("end_date")

            if not start_date or not end_date:
                error_message = "Both start date and end date are required."
            else:
                try:
                    start_date = datetime.strptime(start_date, "%Y-%m-%d")
                    end_date = datetime.strptime(end_date, "%Y-%m-%d")

                    filtered_orders = list(
                        orders_collection.find(
                            {
                                "dateOfCreation": {
                                    "$gte": start_date,
                                    "$lte": end_date,
                                },
                            }
                        )
                    )
                except Exception as e:
                    error_message = f"An error occurred while fetching data: {e}"
    except Exception as e:
        error_message = f"An error occurred: {e}"

    return render_template(
        "orders_summary_nosql.html",
        filtered_orders=filtered_orders,
        error_message=error_message,
    )


@app.route("/orders_summary", methods=["GET", "POST"])
def orders_summary():
    filtered_orders = []
    error_message = None

    if request.method == "POST":
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")

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

            if not order_id or not employee_id:
                error_message = "Both Order ID and Employee ID are required."
            else:
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
            specialization = request.form.get("specialization", "").strip()

        connection = connect_to_database()
        cursor = connection.cursor(dictionary=True)

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
    


@app.route("/usecase_student2_nosql", methods=["GET", "POST"])
def usecase_student2_nosql():
    db = connect_to_mongo()
    orders_coll = db.orders
    employees_coll = db.employees
    error_message = ""
    success_message = ""
    orders = []
    employees = []

    try:
        orders = list(orders_coll.find({}, {"_id": 0}))

        employee_ids = set()

        for order in orders:
            for builder in order.get("assignedBuilders", []):
                if builder["employeeID"] not in employee_ids:
                    employees.append({
                        "employeeID": builder["employeeID"],
                        "name": builder["name"],
                        "email": builder["email"],
                        "isBuilder": "Yes",
                        "role": builder.get("role", ""),
                        "specialization": builder.get("specialization", ""),
                    })
                    employee_ids.add(builder["employeeID"])

        if request.method == "POST":
            order_id = int(request.form["orderID"])
            employee_id = int(request.form["employeeID"])

            order = orders_coll.find_one({"orderID": order_id})
            if not order:
                error_message = f"Order with ID {order_id} does not exist."
            else:
                employee = employees_coll.find_one({"employeeID": employee_id})
                if not employee:
                    error_message = f"Employee with ID {employee_id} does not exist."
                elif not employee.get("isBuilder", False):
                    error_message = f"Employee with ID {employee_id} is not a builder."
                else:
                    if any(builder["employeeID"] == employee_id for builder in order.get("assignedBuilders", [])):
                        error_message = f"Order {order_id} is already assigned to Employee {employee_id}."
                    else:
                        orders_coll.update_one(
                            {"orderID": order_id},
                            {"$push": {"assignedBuilders": {
                                "employeeID": employee["employeeID"],
                                "name": employee["name"],
                                "email": employee["email"],
                                "role": employee.get("role", ""),
                                "specialization": employee.get("specialization", "")
                            }}}
                        )
                        success_message = f"Employee {employee_id} successfully assigned to Order {order_id}."

    except Exception as e:
        error_message = f"An error occurred: {e}"

    return render_template(
        "usecase_student2_nosql.html",
        orders=orders,
        employees=employees,
        error_message=error_message,
        success_message=success_message
    )


@app.route("/report_student2_nosql", methods=["GET", "POST"])
def report_student2_nosql():
    db = connect_to_mongo()
    orders_coll = db.orders
    specialization_filter = None
    builders = []

    try:
        if request.method == "POST":
            specialization_filter = request.form.get("specialization", "").strip()

        orders = list(orders_coll.find({}, {"_id": 0}))

        for order in orders:
            yachts = order.get("yachts", [])
            for builder in order.get("assignedBuilders", []):
                if specialization_filter and builder.get("specialization", "") != specialization_filter:
                    continue

                for yacht in yachts:
                    builders.append({
                        "employeeID": builder["employeeID"],
                        "builderName": builder["name"],
                        "builderRole": builder.get("role", ""),
                        "builderSpecialization": builder.get("specialization", ""),
                        "yachtID": yacht["yachtID"],
                        "yachtModel": yacht.get("model", "N/A"),
                        "yachtLength": yacht.get("length", "N/A"),
                    })

    except Exception as e:
        error_message = f"An error occurred: {e}"
        return render_template("report_student2_nosql.html", builders=[], error_message=error_message)

    return render_template("report_student2_nosql.html", builders=builders)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
