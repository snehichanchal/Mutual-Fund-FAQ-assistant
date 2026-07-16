import os
import sys
import argparse
from rich.console import Console

# Ensure imports work when running from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.guardrails.pii_filter import scan_input
from src.guardrails.intent_classifier import classify_intent
from src.guardrails.refusal_handler import get_refusal_response
from src.retrieval.retriever import retrieve
from src.generation.prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, format_context
from src.generation.llm_client import LLMClient
from src.generation.formatter import format_response

console = Console()

def process_query(query: str) -> None:
    console.print(f"\n[bold blue]User Query:[/bold blue] {query}\n")

    # 1. PII Scan
    with console.status("[yellow]Scanning for PII...[/yellow]"):
        pii_res = scan_input(query)
    
    if pii_res.blocked:
        refusal = get_refusal_response("PII", pii_res.warning_message)
        console.print("[bold red]Blocked by PII Filter:[/bold red]")
        console.print(refusal["answer"])
        return

    # Use the cleaned text from here on
    safe_query = pii_res.cleaned_text

    # 2. Intent Classification
    with console.status("[yellow]Classifying Intent...[/yellow]"):
        intent_res = classify_intent(safe_query)
    
    console.print(f"Intent: [cyan]{intent_res.intent}[/cyan] (Scheme: {intent_res.scheme_name})")

    if intent_res.intent in ["ADVISORY", "OUT_OF_SCOPE", "MALFORMED"]:
        refusal = get_refusal_response(intent_res.intent)
        console.print("[bold red]Refused:[/bold red]")
        console.print(refusal["answer"])
        return

    # 3. Retrieval
    with console.status("[yellow]Retrieving Context...[/yellow]"):
        chunks = retrieve(query=safe_query, scheme_name=intent_res.scheme_name)
    
    if not chunks:
        console.print("[bold red]No context chunks found above the similarity threshold.[/bold red]")
        return

    console.print(f"Retrieved [cyan]{len(chunks)}[/cyan] chunks.")
    
    # 4. Generate Response
    chunks_dicts = [chunk.to_dict() for chunk in chunks]
    context_str = format_context(chunks_dicts)
    
    user_prompt = USER_PROMPT_TEMPLATE.format(
        retrieved_chunks_with_metadata=context_str,
        user_query=safe_query
    )

    with console.status("[yellow]Generating LLM Response...[/yellow]"):
        llm_client = LLMClient()
        llm_output = llm_client.generate_response(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

    if not llm_output:
        console.print("[bold red]Error:[/bold red] Failed to generate response from LLM.")
        return

    # 5. Format Response
    final_result = format_response(llm_output, chunks_dicts)
    
    console.print("\n[bold green]Final Answer:[/bold green]")
    console.print(final_result["answer"])
    console.print(f"\n[dim]{final_result['disclaimer']}[/dim]\n")

def main():
    parser = argparse.ArgumentParser(description="Test the full RAG pipeline in terminal")
    parser.add_argument("--query", "-q", type=str, help="The question to ask")
    args = parser.parse_args()

    if args.query:
        process_query(args.query)
    else:
        # Interactive mode
        console.print("[bold green]Mutual Fund FAQ Assistant CLI (Type 'exit' to quit)[/bold green]")
        while True:
            try:
                q = console.input("\n[bold cyan]Ask >[/bold cyan] ").strip()
                if q.lower() in ['exit', 'quit']:
                    break
                if q:
                    process_query(q)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
