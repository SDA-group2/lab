{
  pkgs ? import <nixpkgs> { },
}:

pkgs.mkShell {
  packages = with pkgs; [
    # Python
    python3
    ruff
    basedpyright
    (pkgs.python3.withPackages (
      python-pkgs: with python-pkgs; [
        pymongo
        python-dotenv
        aio-pika
        requests
      ]
    ))

    # Local testing without an SMTP server
    mailhog

    # API Testing
    hurl
  ];
}
