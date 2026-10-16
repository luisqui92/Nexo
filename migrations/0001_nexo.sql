CREATE TABLE records (
 user_id TEXT NOT NULL,
 id TEXT NOT NULL,
 kind TEXT NOT NULL,
 body TEXT NOT NULL,
 updated TEXT NOT NULL,
 PRIMARY KEY (user_id,id)
);
CREATE INDEX records_by_user_kind ON records(user_id,kind,updated);
CREATE UNIQUE INDEX pending_event_slot ON records(user_id,json_extract(body,'$.date'))
 WHERE kind='events' AND json_extract(body,'$.status')='Pendiente';
CREATE TABLE files (
 user_id TEXT NOT NULL,
 id TEXT NOT NULL,
 record_id TEXT NOT NULL,
 filename TEXT NOT NULL,
 mime TEXT NOT NULL,
 size INTEGER NOT NULL,
 storage TEXT NOT NULL,
 created TEXT NOT NULL,
 PRIMARY KEY(user_id,id),
 FOREIGN KEY(user_id,record_id) REFERENCES records(user_id,id)
);
CREATE TABLE audit (
 id INTEGER PRIMARY KEY,
 user_id TEXT NOT NULL,
 action TEXT NOT NULL,
 record_id TEXT,
 created TEXT NOT NULL
);
CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
