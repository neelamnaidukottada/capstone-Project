SHELL := /bin/sh

.PHONY: dev dev-api dev-web test test-backend test-frontend e2e lint type-check build deploy format clean

dev:
	pnpm dev

dev-api:
	cd backend/apps/api && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	pnpm --filter @acm/web dev

test:
	pnpm test

test-backend:
	pnpm test:backend

test-frontend:
	pnpm test:frontend

e2e:
	pnpm test:e2e

lint:
	pnpm lint

type-check:
	pnpm type-check

format:
	pnpm format

build:
	pnpm build

deploy:
	pnpm deploy

clean:
	pnpm clean
