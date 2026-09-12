from neo4j import GraphDatabase
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class Neo4jService:
    def __init__(self):
        self.driver = None
        try:
            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
            )
            driver.verify_connectivity()
            # Only now, after connectivity is actually confirmed, is self.driver
            # set. Previously self.driver was assigned *before*
            # verify_connectivity() ran, so a failed connectivity check still
            # left a real (but unusable) driver object in place - every
            # `if neo4j_service.driver is None` guard downstream (get_graph,
            # IntelligenceService, the Copilot's context builder) saw a
            # truthy driver and proceeded to query it, silently getting back
            # empty results instead of the 503 those guards were meant to
            # produce. "No graph data" and "Neo4j is unreachable" are very
            # different states and were being reported identically.
            self.driver = driver
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def _session(self):
        # database=None (the default) tells the driver to use whatever the
        # connection's actual default database is. Passing a hardcoded name
        # like "neo4j" breaks on Aura, which gives each instance its own
        # auto-generated default database name.
        return self.driver.session(database=settings.NEO4J_DATABASE or None)

    def execute_write(self, query, parameters=None):
        if not self.driver:
            return None
        with self._session() as session:
            try:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
            except Exception as e:
                logger.error(f"Failed to execute write query: {e}")
                return None

    def execute_read(self, query, parameters=None):
        if not self.driver:
            return None
        with self._session() as session:
            try:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
            except Exception as e:
                logger.error(f"Failed to execute read query: {e}")
                return None

neo4j_service = Neo4jService()
