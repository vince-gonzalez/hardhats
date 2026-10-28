CREATE TABLE logs (
  message TEXT,
  user_id INTEGER REFERENCES users(id),
  tag1 TEXT, tag2 TEXT, tag3 TEXT
);
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT
);
