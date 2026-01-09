# Development Dockerfile - for local frontend dev only
# Production uses the main Dockerfile which builds frontend into the app container

FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
