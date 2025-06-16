create table added (
   order_id             INT4                 not null,
   product_article      INT4                 not null,
   constraint PK_ADDED primary key (order_id, product_article)
);

create unique index added_PK on added (
order_id,
product_article
);

create  index added2_FK on added (
product_article
);

create  index added_FK on added (
order_id
);

create table client (
   client_id            SERIAL               not null,
   user_id              INT4                 not null,
   client_registerdate  DATE                 not null default current_date,
   client_nickname      VARCHAR(128)         not null,
   constraint PK_CLIENT primary key (client_id)
);

create unique index client_PK on client (
client_id
);

create  index client_user_FK on client (
user_id
);

create table courier (
   courier_id           SERIAL               not null,
   user_id              INT4                 not null,
   courier_rating       FLOAT8               not null default 5.00
      constraint CKC_COURIER_RATING_COURIER check (courier_rating between 1.00 and 5.00),
   constraint PK_COURIER primary key (courier_id)
);

create unique index courier_PK on courier (
courier_id
);

create  index courier_user_FK on courier (
user_id
);

create table delivery (
   delivery_id          SERIAL               not null,
   order_id             INT4                 not null,
   courier_id           INT4                 not null,
   delivery_rating      INT4                 not null default 5
      constraint CKC_DELIVERY_RATING_DELIVERY check (delivery_rating between 1 and 5),
   constraint PK_DELIVERY primary key (delivery_id)
);

create unique index delivery_PK on delivery (
delivery_id
);

create  index included_FK on delivery (
order_id
);

create table "order" (
   order_id             SERIAL               not null,
   client_id            INT4                 not null,
   order_status         INT2                 not null default 0
      constraint CKC_ORDER_STATUS_ORDER check (order_status between 0 and 2),
   order_address        VARCHAR(255)         not null,
   order_review         TEXT                 not null default '-',
   constraint PK_ORDER primary key (order_id)
);

comment on column "order".order_status is
'0 - создан
1 - принят курьером
2 - доставлен клиенту';

create unique index order_PK on "order" (
order_id
);

create  index execute_FK on "order" (
client_id
);

create table order_queue (
   courier_id           INT4                 not null,
   delivery_id          INT4                 not null,
   queue_number         INT4                 not null default 1
      constraint CKC_QUEUE_NUMBER_ORDER_QU check (queue_number between 1 and 4),
   constraint PK_ORDER_QUEUE primary key (courier_id, delivery_id)
);

create unique index order_queue_PK on order_queue (
courier_id,
delivery_id
);

create  index Relationship_6_FK on order_queue (
delivery_id
);

create  index Relationship_7_FK on order_queue (
courier_id
);

create table product (
   product_article      INT4                 not null,
   product_name         VARCHAR(128)         not null,
   product_category     VARCHAR(128)         not null,
   product_price        FLOAT8               not null,
   product_description  VARCHAR(512)         not null,
   constraint PK_PRODUCT primary key (product_article)
);

create unique index product_PK on product (
product_article
);

create table users (
   user_id              SERIAL               not null,
   user_tgchat_id       INT8                 not null,
   user_role            VARCHAR(32)          not null,
   user_name            VARCHAR(64)          not null,
   user_surname         VARCHAR(64)          not null,
   user_patronymic      VARCHAR(64)          null,
   user_phonenumber     CHAR(11)             not null,
   user_shortlink       VARCHAR(128)         not null,
   constraint PK_USERS primary key (user_id)
);

comment on column users.user_role is
'client - клиент
courier - courier
admin - администратор';

create unique index users_PK on users (
user_id
);

alter table added
   add constraint FK_ADDED_ADDED_ORDER foreign key (order_id)
      references "order" (order_id)
      on delete restrict on update restrict;

alter table added
   add constraint FK_ADDED_ADDED2_PRODUCT foreign key (product_article)
      references product (product_article)
      on delete restrict on update restrict;

alter table client
   add constraint FK_CLIENT_CLIENT_US_USERS foreign key (user_id)
      references users (user_id)
      on delete restrict on update restrict;

alter table courier
   add constraint FK_COURIER_COURIER_U_USERS foreign key (user_id)
      references users (user_id)
      on delete restrict on update restrict;

alter table delivery
   add constraint FK_DELIVERY_INCLUDED_ORDER foreign key (order_id)
      references "order" (order_id)
      on delete restrict on update restrict;

alter table "order"
   add constraint FK_ORDER_EXECUTE_CLIENT foreign key (client_id)
      references client (client_id)
      on delete restrict on update restrict;

alter table order_queue
   add constraint FK_ORDER_QU_RELATIONS_DELIVERY foreign key (delivery_id)
      references delivery (delivery_id)
      on delete cascade on update restrict;

alter table order_queue
   add constraint FK_ORDER_QU_RELATIONS_COURIER foreign key (courier_id)
      references courier (courier_id)
      on delete cascade on update restrict;