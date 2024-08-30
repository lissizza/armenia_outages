# deploy.sh
if [ "$ENV" == "prod" ]; then
  cp .dockerignore.prod .dockerignore
elif [ "$ENV" == "dev" ]; then
  cp .dockerignore.dev .dockerignore
fi

docker-compose up --build
