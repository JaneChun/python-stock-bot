# 변동성 돌파 전략 백테스트 예시 (삼성전자 2023년)
from pykrx import stock
import pandas as pd
import mplfinance as mpf
import matplotlib

# GUI 없이 이미지 저장용 백엔드 사용 (PowerShell 등 터미널 환경에서 필수)
matplotlib.use('Agg')

df = stock.get_market_ohlcv("20230101", "20231231", "005930")

def volatility_breakout_strategy(df, k = 0.5):
  df = df.astype(float)

  df['range'] = df['고가'] - df['저가'] # 변동폭 = 고가 - 저가
  df['target'] = df['시가'] + df['range'].shift(1) * k  # 매수 목표가 = 시가 + (전일 변동폭 * k)

  # 매수 시그널 = 당일 고가 > 매수 목표가
  df['buy_signal'] = df['고가'] > df['target'] # True/False

  # 매도 시그널 = 당일 종가
  df['sell_price'] = df['종가']

  # 수익률 계산
  df['return'] = 0.0
  profit_ratio = (df['sell_price'] / df['target']) - 1 # 수익률 = 매도가 / 매수가 - 1
  df.loc[df['buy_signal'], 'return'] = profit_ratio # 매수 신호가 있는 날의 수익률을 'return' 컬럼에 저장

  # 누적 수익률 계산
  df['cum_return'] = (1 + df['return']).cumprod()
  final_return = df['cum_return'].iloc[-1]

  # 결과 출력
  print("=== 변동성 돌파 전략 백테스트 (삼성전자 2023) ===")
  print(f"변동성 비율 (k): {k}")
  print(f"최종 누적 수익률: {final_return:.2f}배 ({(final_return-1)*100:.2f}%)")

  return df

def visualise(df):
  # mplfinance를 위한 OHLC 데이터프레임 생성 (영어 컬럼명 필요)
  df_plot = df.copy()
  df_plot = df_plot.rename(columns={
      '시가': 'Open',
      '고가': 'High',
      '저가': 'Low',
      '종가': 'Close'
  })

  # 이동평균선 계산
  df['MA5'] = df['종가'].rolling(window=5).mean()
  df['MA10'] = df['종가'].rolling(window=10).mean()
  df['MA60'] = df['종가'].rolling(window=60).mean()

  # 매수 시그널 마커용 시리즈 생성 (매수 시점에만 target 가격에 마커 표시)
  buy_marker = df['target'].where(df['buy_signal'])

  # 매도 시그널 마커용 시리즈 생성 (매수 시점의 종가에 마커 표시)
  sell_marker = df['종가'].where(df['buy_signal'])

  # 추가 플롯 설정
  apds = [
      # 이동평균선
      mpf.make_addplot(df['MA5'], color='red', width=1.0, panel=0),
      mpf.make_addplot(df['MA10'], color='yellow', width=1.0, panel=0),
      mpf.make_addplot(df['MA60'], color='blue', width=1, panel=0),
      # 매수 목표가 라인 (주황색 점선)
      mpf.make_addplot(df['target'], color='orange', linestyle='--', width=1.5, panel=0, secondary_y=False),
      # 매수 시그널 마커 (녹색 위쪽 삼각형)
      mpf.make_addplot(buy_marker, type='scatter', markersize=20, marker='^', color='lime', panel=0, secondary_y=False),
      # 매도 시그널 마커 (빨간색 아래쪽 삼각형)
      mpf.make_addplot(sell_marker, type='scatter', markersize=20, marker='v', color='magenta', panel=0, secondary_y=False),
      # 누적 수익률 라인 (보라색, 하단 패널)
      mpf.make_addplot(df['cum_return'], color='purple', width=2.0, panel=1, ylabel='누적 수익률 (배)')
  ]

  # 캔들차트 스타일 커스터마이징
  mc = mpf.make_marketcolors(
      up='red',      # 상승 캔들
      down='blue',   # 하락 캔들
      edge='inherit',
      wick='inherit',
      volume='in'
  )
  s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)

  # 캔들스틱 차트 그리기
  mpf.plot(
      df_plot[['Open','High','Low','Close']],
      type='candle',
      style=s,
      mav=(5,10,60),
      addplot=apds,
      volume=False,
      figsize=(16,9),
      title='삼성전자 2023 변동성 돌파 전략\n캔들차트 + 매수시그널 + 누적수익률',
      show_nontrading=False,
      panel_ratios=(3,1),  # 상단:하단 = 3:1 비율
      savefig=dict(fname='samsung_backtest.png', dpi=300)  # 이미지로 저장
  )

result = volatility_breakout_strategy(df, 0.5)
visualise(result)