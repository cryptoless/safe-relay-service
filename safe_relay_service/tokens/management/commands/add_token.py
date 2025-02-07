from django.core.management.base import BaseCommand

from gnosis.eth import EthereumClientProvider
from gnosis.eth.ethereum_client import InvalidERC20Info

from ...models import Token


class Command(BaseCommand):
    help = "Update list of tokens"

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument(
            "tokens", nargs="+", help="Token/s address/es to add to the token list"
        )
        parser.add_argument(
            "--no-prompt",
            help="If set, add the tokens without prompt",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **options):
        tokens = options["tokens"]
        no_prompt = options["no_prompt"]
        ethereum_client = EthereumClientProvider()

        for token_address in tokens:
            token_address = ethereum_client.w3.toChecksumAddress(token_address)
            try:
                token = Token.objects.get(address=token_address)
                self.stdout.write(
                    self.style.WARNING(
                        f"Token {token.name} - {token.symbol} with address "
                        f"{token_address} already exists"
                    )
                )
                continue
            except Token.DoesNotExist:
                pass
            try:
                info = ethereum_client.erc20.get_info(token_address)
                if no_prompt:
                    response = "y"
                else:
                    response = (
                        input(f"Do you want to create a token {info} (y/n) ")
                        .strip()
                        .lower()
                    )
                if response == "y":
                    Token.objects.create(
                        address=token_address,
                        name=info.name,
                        symbol=info.symbol,
                        decimals=info.decimals,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created token {info.name} on address {token_address}"
                        )
                    )
            except InvalidERC20Info:
                self.stdout.write(
                    self.style.ERROR(f"Token with address {token_address} is not valid")
                )
