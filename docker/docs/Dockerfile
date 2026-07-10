FROM node:20-alpine

RUN npm install --global mintlify@4.2.684

WORKDIR /docs
EXPOSE 3000
CMD ["mintlify", "dev", "--host", "0.0.0.0", "--port", "3000"]
