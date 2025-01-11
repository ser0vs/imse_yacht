CREATE DATABASE IF NOT EXISTS yacht_building;

USE yacht_building;

-- Customer Table
CREATE TABLE Customer (
    customerID INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(200)
);

-- CustomerOrder Table
CREATE TABLE CustomerOrder (
    orderID INT PRIMARY KEY AUTO_INCREMENT,
    dateOfCreation DATE,
    price INT,
    customerID INT,
    FOREIGN KEY (customerID) REFERENCES Customer(customerID) ON DELETE CASCADE
);

-- Yacht Table (Composite Primary Key)
CREATE TABLE Yacht (
    yachtID INT,
    orderID INT,
    model VARCHAR(100),
    length INT,
    PRIMARY KEY (yachtID, orderID),
    FOREIGN KEY (orderID) REFERENCES CustomerOrder(orderID) ON DELETE CASCADE
);

-- Employee Table
CREATE TABLE Employee (
    employeeID INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(200)
);

-- Builder Table (Specialized Employee)
CREATE TABLE Builder (
    employeeID INT PRIMARY KEY,
    role VARCHAR(100),
    specialization VARCHAR(100),
    FOREIGN KEY (employeeID) REFERENCES Employee(employeeID) ON DELETE CASCADE
);

-- BuddyOf Table (n:n Relationship)
CREATE TABLE BuddyOf (
    employeeID1 INT,
    employeeID2 INT,
    PRIMARY KEY (employeeID1, employeeID2),
    FOREIGN KEY (employeeID1) REFERENCES Employee(employeeID) ON DELETE CASCADE,
    FOREIGN KEY (employeeID2) REFERENCES Employee(employeeID) ON DELETE CASCADE
);

-- CustomerOrder-Builder Relationship (m:n)
CREATE TABLE CustomerOrderBuilder (
    orderID INT,
    employeeID INT,
    PRIMARY KEY (orderID, employeeID),
    FOREIGN KEY (orderID) REFERENCES CustomerOrder(orderID) ON DELETE CASCADE,
    FOREIGN KEY (employeeID) REFERENCES Builder(employeeID) ON DELETE CASCADE
);