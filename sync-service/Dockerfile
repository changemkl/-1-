FROM node:24-alpine
WORKDIR /app
COPY server.mjs manual-store.mjs ./
RUN mkdir /data && chown node:node /data
USER node
EXPOSE 8788
CMD ["node", "server.mjs"]
