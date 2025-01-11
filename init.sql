CREATE DATABASE IF NOT EXISTS yacht_building;

USE yacht_building;

CREATE TABLE Customer (
                          customerID INT PRIMARY KEY AUTO_INCREMENT,
                          name VARCHAR(100),
                          email VARCHAR(200)
);

CREATE TABLE CustomerOrder (
                               orderID INT PRIMARY KEY AUTO_INCREMENT,
                               dateOfCreation DATE,
                               price INT,
                               customerID INT,
                               FOREIGN KEY (customerID) REFERENCES Customer(customerID) ON DELETE CASCADE
);

CREATE TABLE Yacht (
                       yachtID INT PRIMARY KEY AUTO_INCREMENT,
                       model VARCHAR(100),
                       length INT,
                       orderID INT,
                       FOREIGN KEY (orderID) REFERENCES CustomerOrder(orderID) ON DELETE CASCADE
);

CREATE TABLE Employee (
                          employeeID INT PRIMARY KEY AUTO_INCREMENT,
                          name VARCHAR(100),
                          email VARCHAR(200)
);

CREATE TABLE Builder (
                         employeeID INT PRIMARY KEY,
                         role VARCHAR(100),
                         specialization VARCHAR(100),
                         FOREIGN KEY (employeeID) REFERENCES Employee(employeeID) ON DELETE CASCADE
);

CREATE TABLE BuddyOf (
                         employeeID1 INT,
                         employeeID2 INT,
                         PRIMARY KEY (employeeID1, employeeID2),
                         FOREIGN KEY (employeeID1) REFERENCES Employee(employeeID) ON DELETE CASCADE,
                         FOREIGN KEY (employeeID2) REFERENCES Employee(employeeID) ON DELETE CASCADE
);

CREATE TABLE CustomerOrderBuilder (
                                      orderID INT,
                                      employeeID INT,
                                      PRIMARY KEY (orderID, employeeID),
                                      FOREIGN KEY (orderID) REFERENCES CustomerOrder(orderID) ON DELETE CASCADE,
                                      FOREIGN KEY (employeeID) REFERENCES Builder(employeeID) ON DELETE CASCADE
);
