import os
import mysql.connector
from faker import Faker


def connect_to_database():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpassword"),
        database=os.getenv("DB_NAME", "yacht_building"),
        port=int(os.getenv("DB_PORT", 3306)),
    )


def clear_database(cursor):
    tables = [
        "CustomerOrderBuilder",
        "BuddyOf",
        "Builder",
        "Yacht",
        "CustomerOrder",
        "Employee",
        "Customer",
    ]
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
        cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")


def get_next_yacht_id(cursor):
    cursor.execute("SELECT IFNULL(MAX(yachtID), 0) FROM Yacht")
    return cursor.fetchone()[0] + 1


def populate_database(cursor):
    fake = Faker()

    customers = []
    for _ in range(10):
        name = fake.name()
        email = fake.email()
        cursor.execute(
            "INSERT INTO Customer (name, email) VALUES (%s, %s)", (name, email)
        )
        customers.append(cursor.lastrowid)

    orders = []
    for _ in range(20):
        customer_id = fake.random_element(customers)
        date_of_creation = fake.date_between(start_date="-1y", end_date="today")
        price = fake.random_int(min=10000, max=500000)
        cursor.execute(
            "INSERT INTO CustomerOrder (dateOfCreation, price, customerID) VALUES (%s, %s, %s)",
            (date_of_creation, price, customer_id),
        )
        orders.append(cursor.lastrowid)

    next_yacht_id = get_next_yacht_id(cursor)
    for order_id in orders:
        model = fake.word()
        length = fake.random_int(min=10, max=100)
        cursor.execute(
            "INSERT INTO Yacht (yachtID, model, length, orderID) VALUES (%s, %s, %s, %s)",
            (next_yacht_id, model, length, order_id),
        )
        next_yacht_id += 1


    employees = []
    for _ in range(15):
        name = fake.name()
        email = fake.email()
        cursor.execute(
            "INSERT INTO Employee (name, email) VALUES (%s, %s)", (name, email)
        )
        employees.append(cursor.lastrowid)


    builders = []
    for employee_id in fake.random_sample(employees, 10):
        role = fake.job()
        specialization = fake.word()
        cursor.execute(
            "INSERT INTO Builder (employeeID, role, specialization) VALUES (%s, %s, %s)",
            (employee_id, role, specialization),
        )
        builders.append(employee_id)

    for _ in range(10):
        emp1, emp2 = fake.random_sample(employees, 2)
        cursor.execute(
            "INSERT IGNORE INTO BuddyOf (employeeID1, employeeID2) VALUES (%s, %s)",
            (emp1, emp2),
        )


    used_pairs = set()
    for _ in range(20):
        while True:
            order_id = fake.random_element(orders)
            employee_id = fake.random_element(builders)
            if (order_id, employee_id) not in used_pairs:
                used_pairs.add((order_id, employee_id))
                cursor.execute(
                    "INSERT INTO CustomerOrderBuilder (orderID, employeeID) VALUES (%s, %s)",
                    (order_id, employee_id),
                )
                break


def main():
    connection = connect_to_database()
    cursor = connection.cursor()
    try:
        clear_database(cursor)
        populate_database(cursor)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
