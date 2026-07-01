.PHONY: up down restart logs stop clean refresh

# Start containers:
up:
	docker compose up -d

# Stop containers:
down:
	docker compose down

# Refresh a service: make refresh poller
refresh:
	@$(if $(filter-out refresh,$(MAKECMDGOALS)),,\
		$(error Usage: make refresh <service>  e.g. make refresh poller))
	docker compose up -d --build $(filter-out refresh,$(MAKECMDGOALS))

# Restart containers:
restart:
	docker compose down
	docker compose up -d

# Clean up containers and their volumes / state (DB's):
clean:
	docker compose down -v

# Swallow extra goals from "make refresh <service>"
%:
	@:
