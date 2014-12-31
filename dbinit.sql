drop table if exists snapshots;
drop table if exists exchanges;
drop table if exists trading_pairs;
drop table if exists currencies;
drop table if exists exchange_pairs_map;


create table if not exists currencies (
    id int not null auto_increment,
    uuid char(36),
    updated datetime not null,
    deleted bool not null,
    symbol varchar(10),
    name varchar(10) not null unique,
    description varchar(100),
    primary key (id),
    unique key `currency` (`symbol`)
    );

create table if not exists trading_pairs (
    id int not null auto_increment,
    updated datetime not null,
    deleted bool not null,
    currency_a int not null,
    currency_b int not null,
    primary key (id),
    foreign key (currency_a) references currencies(id) on delete restrict on update cascade,
    foreign key (currency_b) references currencies(id) on delete restrict on update cascade,
    unique key `pair` (`currency_a`,`currency_b`)
    );

create table if not exists exchanges (
    id int not null auto_increment,
    uuid char(36) not null,
    deleted bool not null,
    updated datetime not null,
    name varchar(100) not null unique,
    homepage varchar(100),
    primary key (id),
    unique key `exchange` (`name`)
    );

create table if not exists exchange_pairs_map (
    id int not null auto_increment,
    updated datetime not null,
    deleted bool not null,
    trading_pair int not null,
    exchange int not null,
    primary key (id),
    foreign key (trading_pair) references trading_pairs(id) on delete restrict on update cascade,
    foreign key (exchange) references exchanges(id) on delete restrict on update cascade,
    unique key `map` (`trading_pair`,`exchange`)
    );

create table if not exists snapshots (
    id bigint not null auto_increment,
    exchange int not null,
    trading_pair int not null,
    time time not null,
    last double,
    volume double,
    open double,
    high double,
    low double,
    bid double,
    ask double,
    primary key (id),
    foreign key (exchange) references exchanges(id) on delete restrict on update cascade,
    foreign key (trading_pair) references trading_pairs(id) on delete restrict on update cascade
    );

drop function if exists currency_id;
delimiter $$
create function currency_id(currency_name varchar(10), currency_description varchar(100)) 
    returns int
begin
    declare result_id int;
    select id into result_id from currencies where name = currency_name;
    if result_id is null then
        insert into currencies (name, description) values (currency_name, currency_description);
        set result_id = last_insert_id();
    end if;
    return result_id;
end;
$$
delimiter ;


drop function if exists trading_pair_id;
delimiter $$
create function trading_pair_id(name_a varchar(10), desc_a varchar(100), name_b varchar(10), desc_b varchar(100)) 
    returns int
begin
    declare result_id int;
    declare id1 int;
    declare id2 int;
    set id1 = currency_id(name_a, desc_a);
    set id2 = currency_id(name_b, desc_b);
    select id into result_id from trading_pairs where currency_a = id1 and currency_b = id2;
    if result_id is null then
        insert into trading_pairs (currency_a, currency_b) values (id1, id2);
        set result_id = last_insert_id();
    end if;
    return result_id;
end;
$$
delimiter ;

drop function if exists exchange_id;
delimiter $$
create function exchange_id(e_name varchar(100), e_homepage varchar(100)) 
    returns int
begin
    declare result_id int;
    select id into result_id from exchanges where name = e_name;
    if result_id is null then
        insert into exchanges (name, homepage) values (e_name, e_homepage);
        set result_id = last_insert_id();
    end if;
    return result_id;
end;
$$
delimiter ;
