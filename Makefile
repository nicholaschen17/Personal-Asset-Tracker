.PHONY: up down restart logs stop clean

# Start containers:
up:
	docker compose up -d

# Stop containers:
down:
	docker compose down

# Restart containers:
restart:
	docker compose down
	docker compose up -d

# Clean up containers and their volumes / state (DB's):
clean:
	docker compose down -v

