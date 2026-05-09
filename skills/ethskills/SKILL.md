---
name: ethskills
description: >
  Ethereum ecosystem tooling and standards reference. TRIGGER when: asking
  about Ethereum development tools, framework selection, RPC providers, block
  explorers, EIP/ERC standards, or general Web3 development workflow. DO NOT
  TRIGGER when: writing or auditing Solidity code (use solidity-audit skill),
  or working with Noir/ZK circuits (use noir skill).
metadata:
  author: DROOdotFOO
  version: "1.0.0"
  tags: ethereum, web3, foundry, blockscout, eip, erc, tooling
---

# ethskills

Ethereum ecosystem tooling, framework selection, and standards reference.
For Solidity code and auditing, use solidity-audit. For ZK/Noir, use noir.

## What You Get

- Framework comparison (Foundry vs Hardhat vs Scaffold-ETH 2)
- RPC provider, block explorer, and faucet reference
- EIP/ERC standards lookup with status and usage guidance
- Blockscout MCP and abi.ninja tool patterns

## When to use

This skill activates for ecosystem-level questions: which tools to use,
how to configure infrastructure, which standards apply, where to find
resources.

## When NOT to use

- For Solidity code or security auditing -- use solidity-audit
- For Noir/ZK circuit design -- use noir
- For non-Ethereum languages -- use droo-stack

## See also

- `blockscout` -- full Blockscout MCP tool reference (16 tools, usage patterns)
- `coingecko` -- crypto market data, token prices, DEX pools, trending tokens
- `sentinel` -- automated on-chain contract monitoring with alert rules
- `solidity-audit` -- for EIP/ERC implementation guidance and security review
- `noir` -- for ZK circuit patterns and Aztec contract integration
- `zk-x-ray` -- for pre-EIP audit briefings on ZK + EVM hybrid protocols
- `design-ux` -- for dApp frontend design patterns

## Reading guide

| Question                                    | Read                                  |
| ------------------------------------------- | ------------------------------------- |
| Foundry commands, Blockscout MCP, abi.ninja | [tools](tools.md)                     |
| Foundry vs Hardhat vs Scaffold-ETH 2        | [stack-selection](stack-selection.md) |
| RPC providers, block explorers, faucets     | [rpc-explorers](rpc-explorers.md)     |
| EIP/ERC standards reference                 | [standards](standards.md)             |
| Full Blockscout MCP tool reference          | blockscout skill                      |
| Token prices, DEX pools, market data        | coingecko skill                       |
