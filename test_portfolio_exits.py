#!/usr/bin/env python3
"""
Test script for portfolio exit checking functionality
"""
import sys
import asyncio
from datetime import datetime

# Test the portfolio exit checking
async def test_portfolio_exits():
    """Test the portfolio exit checking functionality"""
    print("🧪 TESTING PORTFOLIO EXIT CHECKING")
    print("=" * 50)
    
    try:
        # Import the production trader
        from production_trader_win import ProductionAutoTrader
        
        # Create trader instance in dry-run mode
        trader = ProductionAutoTrader(dry_run=True, paper_trading=True, test_mode=True)
        
        print("✅ Production trader created successfully")
        
        # Test portfolio exit checking
        print("\n📊 Testing portfolio exit check method...")
        exit_signals = await trader.check_portfolio_exits()
        
        print(f"✅ Exit check completed - Found {len(exit_signals)} signals")
        
        if exit_signals:
            print("\n🎯 EXIT SIGNALS FOUND:")
            for signal in exit_signals:
                print(f"   {signal.get('ticker', 'N/A')} - {signal.get('action', 'N/A')} - {signal.get('reason', 'N/A')}")
        else:
            print("   No exit signals (positions within targets)")
        
        # Test full signal generation
        print("\n📈 Testing full signal generation...")
        all_signals = await trader.get_todays_signals('OPEN')
        
        print(f"✅ Signal generation completed - Found {len(all_signals)} total signals")
        
        exit_count = len([s for s in all_signals if s.get('signal_type') == 'EXIT_SIGNAL'])
        entry_count = len(all_signals) - exit_count
        
        print(f"   📤 Exit signals: {exit_count}")
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
        result = asyncio.run(test_portfolio_exits())
        if result:
            print("\n🎉 Portfolio exit testing completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Portfolio exit testing failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Async test failed: {e}")
        sys.exit(1)
