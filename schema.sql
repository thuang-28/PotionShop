CREATE TABLE global_inventory (
    id bigint NOT NULL,
    num_red_ml integer DEFAULT 0 NOT NULL,
    num_green_ml integer DEFAULT 0 NOT NULL,
    num_blue_ml integer DEFAULT 0 NOT NULL,
    num_dark_ml integer DEFAULT 0 NOT NULL,
    gold integer DEFAULT 100 NOT NULL,
    potion_capacity integer DEFAULT 1 NOT NULL,
    ml_capacity integer DEFAULT 1 NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE potion_inventory (
    sku text NOT NULL,
    quantity integer DEFAULT 0 NOT NULL,
    red integer DEFAULT 0 NOT NULL,
    green integer DEFAULT 0 NOT NULL,
    blue integer DEFAULT 0 NOT NULL,
    dark integer DEFAULT 0 NOT NULL,
    PRIMARY KEY (sku)
);

CREATE TABLE customers (
    id bigint NOT NULL,
    visited_at timestamp with time zone DEFAULT now() NOT NULL,
    name text NOT NULL,
    class text NOT NULL,
    level integer NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE carts (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    customer_id bigint NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE cart_items (
    cart_id bigint NOT NULL,
    sku text NOT NULL,
    quantity integer DEFAULT 0 NOT NULL,
    PRIMARY KEY (cart_id, sku),
    FOREIGN KEY (cart_id) REFERENCES carts(id),
    FOREIGN KEY (sku) REFERENCES potion_inventory(sku)
);