I will set up and launch the project in "Hybrid Mode": databases in Docker, and the code (Frontend/Backend) running locally for the best development experience.

### 1. Configure Environment

* Create a `.env` file based on `.env.example`.

* Configure local connection strings:

  * **Neo4j**: `bolt://localhost:7687` (User: `neo4j`, Pass: `password`)

  * **Postgres**: `postgresql://postgres:root:localhost:5432/cultur`**Qdrant**: `http://localhost:6333`

  * **JWT Secret**: Set a default development secret.

## 2. Start Backend (Python)

* Create a virtual environment (`.venv`) and install dependencies from `requirements.txt`.

* Run the FastAPI server using `uvicorn`.

### 3. Start Frontend (React)

* Install Node.js dependencies (`npm install`).

* Start the development server (`npm run dev`).

