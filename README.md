# Computer Architecture Formula Sheet

A comprehensive reference for performance analysis, I/O systems, memory hierarchies, and pipelining.

---

## 1. Pipelined vs Non-Pipelined Speedup

### Time per instruction

$$T = \frac{\text{CPI}}{\text{Clock Frequency}}$$

### Effective CPI with stalls

$$\text{CPI}_{\text{pipe}} = \text{Ideal CPI} + \sum (f_i \times s_i)$$

### Speedup

$$\text{Speedup} = \frac{T_{\text{non}}}{T_{\text{pipe}}} = \frac{\text{CPI}_{\text{non}} \times f_{\text{pipe}}}{\text{CPI}_{\text{pipe}} \times f_{\text{non}}}$$

### Variables

- $\text{CPI}$ → Cycles Per Instruction
- $f$ → Clock frequency (Hz)
- $f_i$ → Fraction of instructions causing hazard $i$
- $s_i$ → Stall cycles for hazard $i$
- $T_{\text{non}}, T_{\text{pipe}}$ → Time per instruction in each design

### Example

Non-pipelined: 1.6 GHz, CPI = 5. Pipelined: 1.2 GHz, 20% stall 2 cycles.

- $\text{CPI}_{\text{pipe}} = 1 + (0.2 \times 2) = 1.4$
- $\text{Speedup} = \frac{5 \times 1.2}{1.4 \times 1.6} = \frac{6}{2.24} \approx 2.68$

---

## 2. Amdahl's Law with Multicore Overhead

### Generalized execution time

$$T(N) = T_s + \frac{T_p}{N} + \text{Overhead}(N)$$

### Speedup (Amdahl's classic)

$$S = \frac{1}{(1-p) + \frac{p}{N}}$$

### Variables

- $T_s$ → Serial (non-parallelizable) time
- $T_p$ → Parallelizable time
- $N$ → Number of cores
- $p$ → Fraction parallelizable

### Optimization rule

- **Overhead constant** → more cores always better (∞ optimal)
- **Overhead per extra core** → differentiate $\frac{dT}{dN} = 0$ for optimal $N$

### Example

$T_s = 10$, $T_p = 90$, overhead $= 10(N-1)$.

- $T(N) = \frac{90}{N} + 10N$
- $\frac{dT}{dN} = -\frac{90}{N^2} + 10 = 0$ → $N^2 = 9$ → **N = 3 cores**

---

## 3. Disk Access Time

### Time per rotation

$$T_{\text{rot}} = \frac{60}{\text{RPM}} \text{ seconds}$$

### Average rotational latency

$$L_{\text{avg}} = \frac{T_{\text{rot}}}{2}$$

### Transfer time per sector

$$T_{\text{xfer}} = \frac{T_{\text{rot}}}{\text{Sectors per track}}$$

### Total time per sector access

$$T_{\text{sector}} = T_{\text{seek}} + L_{\text{avg}} + T_{\text{xfer}}$$

### Total file read time

$$T_{\text{total}} = N_{\text{sectors}} \times T_{\text{sector}}$$

### Variables

- $T_{\text{seek}}$ → Seek time (head positioning)
- $L_{\text{avg}}$ → Average rotational latency
- $T_{\text{xfer}}$ → Sector transfer time
- $N_{\text{sectors}}$ → Number of sectors to read

### Example

Seek = 4 ms, RPM = 10000, 600 sectors/track, file = 2000 sectors.

- $T_{\text{rot}} = 60/10000 = 6$ ms
- $L_{\text{avg}} = 3$ ms; $T_{\text{xfer}} = 6/600 = 0.01$ ms
- Per sector $= 4 + 3 + 0.01 = 7.01$ ms
- Total $= 2000 \times 7.01 = $ **14020 ms**

---

## 4. Disk Access (with Controller Overhead)

### Disk transfer time per sector

$$T_{\text{disk}} = \frac{\text{Sector size}}{\text{Transfer rate}}$$

### Controller transfer time

$$T_{\text{ctrl}} = k \times T_{\text{disk}}$$

### Total

$$T_{\text{total}} = T_{\text{seek}} + L_{\text{avg}} + T_{\text{disk}} + T_{\text{ctrl}}$$

### Example

RPM = 15000, 50 MB/s, 512 B sector, seek = 2× rot delay, ctrl = 10× disk transfer.

- $T_{\text{rot}} = 4$ ms → $L_{\text{avg}} = 2$ ms → seek = 4 ms
- $T_{\text{disk}} = 512/(50 \times 10^6) = 0.01024$ ms; $T_{\text{ctrl}} = 0.1024$ ms
- Total $= 4 + 2 + 0.01024 + 0.1024 \approx$ **6.11 ms**

---

## 5. Polling vs Interrupt I/O

### Inter-arrival time of bytes

$$T_{\text{arrival}} = \frac{1}{\text{Data rate (bytes/sec)}}$$

### Performance gain (Interrupt over Polling)

$$\text{Gain} = \frac{T_{\text{arrival}}}{T_{\text{interrupt}}}$$

### Variables

- $T_{\text{arrival}}$ → Time between successive bytes
- $T_{\text{interrupt}}$ → CPU time to service one interrupt

### Example

10 KB/s, interrupt overhead = 4 µs/byte.

- $T_{\text{arrival}} = 1/10240 \approx 97.65$ µs
- Gain $= 97.65/4 \approx$ **24.41**

---

## 6. DMA Cycle Stealing — CPU Blocking Percentage

### Disk transfer rate

$$R = \text{Bytes per rotation} \times \text{RPS}$$

### DMA cycles per second

$$N_{\text{DMA}} = \frac{R}{\text{Bytes per DMA cycle}}$$

### CPU blocking fraction

$$\text{Blocking \%} = N_{\text{DMA}} \times T_{\text{mem}} \times 100$$

### Shortcut form

$$\text{Blocking \%} = \frac{R}{B_{\text{DMA}}} \times T_{\text{mem}}$$

### Variables

- $R$ → Disk transfer rate (bytes/sec)
- $B_{\text{DMA}}$ → Bytes per DMA transfer
- $T_{\text{mem}}$ → Memory cycle time
- $N_{\text{DMA}}$ → DMA cycles per second

### Example

3000 RPM, 512 sectors × 1 KB, 4 B/DMA, 40 ns memory cycle.

- $R = 50 \times 524288 = 26{,}214{,}400$ B/s
- $N_{\text{DMA}} = 6{,}553{,}600$/s
- Blocking $= 6{,}553{,}600 \times 40 \times 10^{-9} \approx$ **26.2%**

---

## 7. Cache — Average Memory Access Time (AMAT)

### Core formula

$$\text{AMAT} = T_{\text{hit}} + (\text{Miss rate} \times \text{Miss penalty})$$

### Miss penalty (block fetch)

$$\text{Miss penalty} = T_{\text{first}} + (W - 1) \times T_{\text{rest}}$$

### Words per block

$$W = \frac{\text{Block size}}{\text{Word size}}$$

### Variables

- $T_{\text{hit}}$ → Cache access time on hit
- $T_{\text{first}}$ → Time to fetch first word from main memory
- $T_{\text{rest}}$ → Time per subsequent word
- $W$ → Words per block

### Example

Hit = 3 ns, miss rate = 0.06, block = 256 B, word = 8 B, first = 20 ns, rest = 5 ns.

- $W = 32$; Miss penalty $= 20 + 31 \times 5 = 175$ ns
- AMAT $= 3 + 0.06 \times 175 =$ **13.5 ns**

**Note:** Do not add hit time again inside the miss branch — it is already counted.

---

## 8. DRAM Refresh Overhead

### Total refresh time per period

$$T_{\text{refresh}} = N_{\text{rows}} \times T_{\text{row}}$$

### Refresh overhead fraction

$$\text{Overhead} = \frac{T_{\text{refresh}}}{T_{\text{period}}}$$

### Time available for read/write

$$\text{Useful \%} = (1 - \text{Overhead}) \times 100$$

### Variables

- $N_{\text{rows}}$ → Total rows to refresh (often $2^k$)
- $T_{\text{row}}$ → Time to refresh one row
- $T_{\text{period}}$ → Refresh interval (e.g., 2 ms)

### Example

$2^{14} = 16384$ rows, 50 ns/row, 2 ms period.

- $T_{\text{refresh}} = 16384 \times 50 = 819{,}200$ ns
- Overhead $= 819200/(2 \times 10^6) = 0.4096$
- Useful $\approx$ **59%**

**Note:** Capacity, chip count, and width are red herrings — only rows and timing matter.

---

## Quick Reference Table

| Scenario | Trigger phrase | Formula to reach for |
|---|---|---|
| Pipeline speedup | "stall cycles", "hazards" | $\text{CPI}_{\text{pipe}} = 1 + \sum f_i s_i$ |
| Multicore | "parallelizable", "cores" | Amdahl + overhead model |
| Disk read | "seek", "RPM", "sectors" | Seek + Latency + Transfer |
| I/O method | "polling vs interrupt" | $T_{\text{arrival}}/T_{\text{interrupt}}$ |
| DMA blocking | "cycle stealing" | $R \times T_{\text{mem}} / B_{\text{DMA}}$ |
| Cache | "hit rate", "miss penalty" | AMAT |
| DRAM | "refresh", "rows" | Refresh fraction |

---

**End of Formula Sheet**
