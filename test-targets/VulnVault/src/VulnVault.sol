// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

// Deliberately-vulnerable fixture for validating the security-audit pipeline and
// the distilled knowledge library. NOT production code. Each bug corresponds to
// a pattern in .claude/skills/security-audit/knowledge/.

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address a) external view returns (uint256);
}

interface IAggregator {
    function latestRoundData()
        external view returns (uint80, int256, uint256, uint256, uint80);
}

contract VulnVault {
    IERC20 public asset;
    IAggregator public priceFeed;
    address public owner;
    uint256 public totalShares;
    mapping(address => uint256) public shares;
    mapping(address => uint256) public balance;

    constructor(address _asset, address _feed) {
        asset = IERC20(_asset);
        priceFeed = IAggregator(_feed);
        owner = msg.sender;
    }

    // Deposit assets, receive shares.
    function deposit(uint256 amount) external {
        asset.transferFrom(msg.sender, address(this), amount);     // return value ignored
        uint256 price = _price();
        // round-UP share math favors the depositor; pool runs a dust deficit
        uint256 minted = (amount * price + 1e18 - 1) / 1e18;
        shares[msg.sender] += minted;
        totalShares += minted;
        balance[msg.sender] += amount;
    }

    // Withdraw: sends ETH BEFORE updating balances -> reentrancy, no guard.
    function withdraw() external {
        uint256 bal = balance[msg.sender];
        require(bal > 0, "no balance");
        (bool ok, ) = msg.sender.call{value: bal}("");             // external call first
        require(ok, "send failed");
        balance[msg.sender] = 0;                                   // state update after
        shares[msg.sender] = 0;
    }

    // Price from oracle, consumed with no staleness / completeness checks.
    function _price() internal view returns (uint256) {
        (, int256 answer, , , ) = priceFeed.latestRoundData();     // no updatedAt / answeredInRound / >0 check
        return uint256(answer);
    }

    // Anyone can retarget the price feed -> missing access control, no timelock.
    function setPriceFeed(address _feed) external {
        priceFeed = IAggregator(_feed);                            // should be onlyOwner + timelock
    }

    // Owner sweep uses raw transfer, return ignored.
    function sweep(address token, address to, uint256 amt) external {
        require(msg.sender == owner, "not owner");
        IERC20(token).transfer(to, amt);                          // return value ignored
    }

    receive() external payable {}
}
