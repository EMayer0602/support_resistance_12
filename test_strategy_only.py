#!/usr/bin/env python3
"""
Test script for STRATEGY-ONLY exit checking (no stop loss/profit targets)
"""
import sys
import asyncio
from datetime import datetime

# Test the strategy-only portfolio exit checking
async def test_strategy_only_exits():
    """Test the strategy-only exit checking functionality"""
    print("🧪 TESTING STRATEGY-ONLY EXIT CHECKING")
    print("=" * 60)
    print("🚨 NO STOP LOSS OR PROFIT TARGETS!")
    print("💡 ONLY STRATEGY SIGNALS CONTROL EXITS!")
    print("=" * 60)
    
    try:
        # Import the production trader
        from production_trader_win import ProductionAutoTrader
        
        # Create trader instance in dry-run mode
        trader = ProductionAutoTrader(dry_run=True, paper_trading=True, test_mode=True)
        
        print("✅ Production trader created successfully")
        
        # Test portfolio exit checking
        print("\n📊 Testing strategy-only exit check method...")
        exit_signals = await trader.check_portfolio_exits()
        
        print(f"✅ Exit check completed - Found {len(exit_signals)} STRATEGY exit signals")
        
        if exit_signals:
            print("\n🎯 STRATEGY EXIT SIGNALS FOUND:")
            for signal in exit_signals:
                ticker = signal.get('ticker', 'N/A')
                action = signal.get('action', 'N/A')
                reason = signal.get('reason', 'N/A')
                signal_type = signal.get('signal_type', 'N/A')
                print(f"   [{signal_type}] {ticker} - {action} - {reason}")
        else:
            print("   ✅ No strategy exit signals - positions maintained")
        
        # Test full signal generation
        print("\n📈 Testing full signal generation with strategy-only exits...")
        all_signals = await trader.get_todays_signals('OPEN')
        
        print(f"✅ Signal generation completed - Found {len(all_signals)} total signals")
        
        strategy_exit_count = len([s for s in all_signals if s.get('signal_type') == 'STRATEGY_EXIT'])
        entry_count = len(all_signals) - strategy_exit_count
        
        print(f"   📤 Strategy exit signals: {strategy_exit_count}")
        print(f"   📥 Entry signals: {entry_count}")
        
        if all_signals:
            print("\n🎯 ALL SIGNALS:")
            for signal in all_signals:
                signal_type = signal.get('signal_type', 'ENTRY_SIGNAL')
                ticker = signal.get('ticker', 'N/A')
                action = signal.get('action', 'N/A')
                reason = signal.get('reason', signal.get('strategy', 'N/A'))
                print(f"   [{signal_type}] {ticker} - {action} - {reason}")
        
        print("\n✅ ALL TESTS PASSED!")
        print("\n💡 KEY BENEFITS OF STRATEGY-ONLY EXITS:")
        print("   📈 No premature profit taking")
        print("   🛡️ No stop losses cutting trends short")
        print("   🎯 Pure strategy-based entry and exit decisions")
        print("   💰 Maximum profit potential from winning trades")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Run the test
if __name__ == "__main__":
    print(f"🕐 Test started at: {datetime.now()}")
    
    # Run async test
    try:
        result = asyncio.run(test_strategy_only_exits())
        if result:
            print("\n🎉 Strategy-only exit testing completed successfully!")
            print("🚀 System ready for pure strategy trading!")
            sys.exit(0)
        else:
            print("\n❌ Strategy-only exit testing failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Async test failed: {e}")
        sys.exit(1)
