from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "sentinel_neo4j_password")

class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def merge_auth_graph(self, routes_data: list[dict]):
        with self.driver.session() as session:
            for route in routes_data:
                session.execute_write(self._create_route_node, route)

    @staticmethod
    def _create_route_node(tx, route: dict):
        query = """
        MERGE (r:Route {path: $path, method: $method})
        SET r.function_name = $function_name
        
        // Loop over guards and connect them
        WITH r
        UNWIND $guards AS guard_name
        MERGE (g:Guard {name: guard_name})
        MERGE (g)-[:PROTECTS]->(r)
        
        // Connect to resources (derived loosely from the path or arguments)
        WITH r, [p in $arguments WHERE p <> "current_user"] AS resources
        UNWIND resources AS res_name
        MERGE (res:Resource {name: res_name})
        MERGE (r)-[:ACCESSES]->(res)
        """
        tx.run(query, 
               path=route.get("path"), 
               method=route.get("method"), 
               function_name=route.get("function_name"), 
               guards=route.get("guards", []),
               arguments=route.get("arguments", []))

neo_client = Neo4jClient()
