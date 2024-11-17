create table
  public.potion_index (
    sku text not null default 'COLOR_POTION'::text,
    price integer not null default 35,
    red_pct integer not null default 0,
    green_pct integer not null default 0,
    blue_pct integer not null default 0,
    dark_pct integer not null default 0,
    bottle_limit integer not null default 35,
    constraint potion_index_pkey primary key (sku)
  ) tablespace pg_default;

CREATE TYPE public.day of week AS ENUM ('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday');

create table
  public.potion_strategy (
    day_of_week public.day of week not null,
    potion_sku text not null,
    favorability real not null default '1.5'::real,
    constraint potion_strategy_pkey primary key (day_of_week, potion_sku),
    constraint potion_strategy_potion_sku_fkey foreign key (potion_sku) references potion_index (sku) on update cascade
  ) tablespace pg_default;

create table
  public.customer_visits (
    id bigint generated by default as identity not null,
    timestamp timestamp with time zone not null default now(),
    name text not null,
    class text not null,
    day_of_week text not null default to_char(now(), 'fmDay'::text),
    level integer not null,
    constraint customer_visits_pkey primary key (id)
  ) tablespace pg_default;

create table public.carts (
    id bigint generated by default as identity not null,
    timestamp timestamp with time zone not null default now(),
    customer_name text not null,
    customer_class text not null,
    level integer not null,
    day_of_week text not null default to_char(now(), 'fmDay' :: text),
    constraint customers_pkey primary key (id)
) tablespace pg_default;

create table
  public.cart_items (
    cart_id bigint not null,
    sku text not null,
    quantity integer not null,
    timestamp timestamp with time zone not null default now(),
    day_of_week text not null default to_char(now(), 'fmDay'::text),
    item_id bigint generated by default as identity not null,
    constraint cart_items_pkey primary key (cart_id, sku),
    constraint cart_items_item_id_key unique (item_id),
    constraint cart_items_cart_id_fkey foreign key (cart_id) references carts (id),
    constraint cart_items_sku_fkey foreign key (sku) references potion_index (sku) on update cascade
  ) tablespace pg_default;

create table public.capacity_records (
    id bigint generated by default as identity not null,
    potion_units integer not null default 1,
    ml_units integer not null default 1,
    timestamp timestamp with time zone not null default now(),
    constraint capacity_units_pkey primary key (id)
) tablespace pg_default;

create table public.gold_records (
    id bigint generated by default as identity not null,
    change_in_gold integer not null default 100,
    timestamp timestamp with time zone not null default now(),
    day_of_week text not null default to_char(now(), 'fmDay' :: text),
    constraint gold_transactions_pkey primary key (id)
) tablespace pg_default;

create table
  public.potion_records (
    sku text not null,
    qty_change integer not null,
    timestamp timestamp with time zone not null default now(),
    id integer generated by default as identity not null,
    day_of_week text not null default to_char(now(), 'fmDay'::text),
    constraint potion_records_pkey primary key (id),
    constraint potion_records_sku_fkey foreign key (sku) references potion_index (sku) on update cascade
  ) tablespace pg_default;

create table public.ml_records (
    id bigint generated by default as identity not null,
    red integer not null default 0,
    green integer not null default 0,
    blue integer not null default 0,
    dark integer not null default 0,
    timestamp timestamp with time zone not null default now(),
    constraint ml_inventory_pkey primary key (id)
) tablespace pg_default;
 
 
INSERT INTO gold_records DEFAULT VALUES;

INSERT INTO capacity_records DEFAULT VALUES;