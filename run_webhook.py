import argparse
import uvicorn


def main():
    """
    Run the REDCap EDT webhook using Uvicorn.     
    """
    parser = argparse.ArgumentParser(
        description="Run REDCap EDT webhook"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)" 
    )
    parser.add_argument(
        "--port",
        default=8000,
        type=int,
        help="Bind port (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (default: False)"
    )
    args = parser.parse_args()

    uvicorn.run(
        "integracao_emprace.webhook:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()