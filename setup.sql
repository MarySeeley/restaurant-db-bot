-- Food category (Appetizer, Entree, Dessert, Drink)
CREATE TABLE category (
    category_id INTEGER PRIMARY KEY,
    name        VARCHAR(30) NOT NULL COLLATE NOCASE
);

-- Items available on the menu
CREATE TABLE menu_item (
    item_id     INTEGER PRIMARY KEY,
    name        VARCHAR(60)  NOT NULL COLLATE NOCASE,
    description VARCHAR(150)          COLLATE NOCASE,
    price       DECIMAL(6, 2) NOT NULL,
    category_id INTEGER NOT NULL,
    FOREIGN KEY (category_id) REFERENCES category (category_id)
);

-- Customers who place orders
CREATE TABLE customer (
    customer_id INTEGER PRIMARY KEY,
    name        VARCHAR(60) NOT NULL COLLATE NOCASE,
    email       VARCHAR(80)          COLLATE NOCASE,
    phone       VARCHAR(15)
);

-- Restaurant employees
CREATE TABLE staff (
    staff_id    INTEGER PRIMARY KEY,
    name        VARCHAR(60) NOT NULL COLLATE NOCASE,
    role        VARCHAR(30) NOT NULL COLLATE NOCASE,
    hourly_rate DECIMAL(5, 2) NOT NULL,
    hire_date   DATE NOT NULL
);

-- A single table visit / order (customer + staff member who served them)
CREATE TABLE restaurant_order (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    staff_id    INTEGER NOT NULL,
    order_date  DATE NOT NULL,
    table_number INTEGER NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customer (customer_id),
    FOREIGN KEY (staff_id)    REFERENCES staff    (staff_id)
);

-- Individual items within an order
CREATE TABLE order_item (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    item_id       INTEGER NOT NULL,
    quantity      INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (order_id) REFERENCES restaurant_order (order_id),
    FOREIGN KEY (item_id)  REFERENCES menu_item        (item_id)
);

-- Customer reviews of their experience
CREATE TABLE review (
    review_id   INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    rating      INTEGER NOT NULL,  -- 1-5 stars
    comment     VARCHAR(300),
    review_date DATE NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customer (customer_id)
);
