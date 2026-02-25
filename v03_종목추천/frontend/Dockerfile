FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3101

CMD ["npm", "run", "dev"]
