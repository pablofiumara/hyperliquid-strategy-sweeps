.PHONY: start stop restart logs import clean psql

start:
	docker compose up -d --build
	@echo ""; echo "app:  http://localhost:8080   api: http://localhost:8000/docs"

stop:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

import:
	curl -s -X POST http://localhost:8080/api/import | head -c 400; echo

psql:
	docker compose exec db psql -U hl -d hl

clean:
	docker compose down -v
