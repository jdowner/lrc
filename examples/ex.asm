start:
  LDA 9
  STA iteration + 1
iteration:
  NUL
print:
  CMP iteration + 1, iteration
  BRB done
  LDA 65
  STA 0
  LDA 108
  STA 0
  LDA 101
  STA 0
  LDA 120
  STA 0
  LDA 10
  STA 0
  INC iteration
  JMP print
done:
  HLT
