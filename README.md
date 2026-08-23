# customer-support-agent

                    User
                      │
                      ↓
                   React
                      │
                     SSE
                      │
                      ↓
                  FastAPI
                      │
                      ↓
                 LangGraph
                      │
             ┌────────┼─────────┐
             ↓        ↓         ↓
          Search    Order     Refund
           Tool      Tool       Tool
             │        │          │
             ↓        ↓          ↓
           RAG      Database    API
                      │
                      ↓
                  PostgreSQL
