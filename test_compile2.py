import requests
import urllib.parse

latex_code = r"""
\documentclass{standalone}
\usepackage[siunitx, american]{circuitikz}
\usepackage{tikz}

\begin{document}

\begin{tikzpicture}[scale=0.95, every node/.style={transform shape}]

    % 1. Left Input Section
    \draw[thick] (-2.2, 4.0) -- (-1.8, 4.0) -- (-1.8, 3.2) -- (-1.2, 3.2) -- (-1.2, 4.0) -- (-0.8, 4.0);
    \draw (-0.5, 3.5) node[left, font=\large] {$V_{\mathrm{PWM, P(N)}}$};
    \draw (-0.5, 3.5) to[short, -o] (0.2, 3.5);
    \draw (0.2, 3.5) -- (1.5, 3.5);
    \draw[thick] (1.5, 7.5) -- (1.5, -0.5);

    % 2. Top Stack (M1, M2, M3)
    \draw (3.5, 8.2) node[vcc] {$V_{DD}$};
    \draw (3.5, 7.5) node[pmos, bulk] (M1) {};
    \draw (3.5, 6.0) node[pmos, bulk] (M2) {};
    \draw (3.5, 4.5) node[nmos, bulk] (M3) {};
    \draw (3.5, 3.8) node[ground] {};

    \draw (3.5, 8.0) -- (M1.S);
    \draw (M1.D) -- (M2.S);
    \draw (M2.D) -- (M3.D);
    \draw (M3.S) -- (3.5, 4.0);

    \draw (1.5, 7.5) -- (M1.G);
    \draw (1.5, 4.5) -- (M3.G);

    % 3. Bottom Stack (M4, M5, M6)
    \draw (3.5, 3.2) node[vcc] {$V_{DD}$};
    \draw (3.5, 2.5) node[pmos, bulk] (M4) {};
    \draw (3.5, 1.0) node[nmos, bulk] (M5) {};
    \draw (3.5, -0.5) node[nmos, bulk] (M6) {};
    \draw (3.5, -1.2) node[ground] {};

    \draw (3.5, 3.0) -- (M4.S);
    \draw (M4.D) -- (M5.D);
    \draw (M5.S) -- (M6.D);
    \draw (M6.S) -- (3.5, -1.0);

    \draw (1.5, 2.5) -- (M4.G);
    \draw (1.5, -0.5) -- (M6.G);
    \node[left, font=\large] at (2.8, 1.0) {EN};

    % 4. Inverter Chains
    \draw (M2.D) -- (4.5, 5.25);
    \draw (4.5, 5.25) -- (4.8, 5.25) -- (4.8, 5.75) to[not port] (6.2, 5.75);
    \draw (4.8, 5.25) -- (4.8, 4.75) to[not port] (6.2, 4.75);

    \draw (M5.D) -- (4.5, 1.75);
    \draw (4.5, 1.75) -- (4.8, 1.75) -- (4.8, 2.25) to[not port] (6.2, 2.25);
    \draw (4.8, 1.75) -- (4.8, 1.25) to[not port] (6.2, 1.25);

    % 5. Output Stages
    \draw (8.0, 6.7) node[vcc] {$V_{DD}$};
    \draw (8.0, 6.0) node[pmos, bulk] (MO1) {};
    \draw (8.0, 4.5) node[nmos, bulk] (MO2) {};
    \draw (8.0, 3.8) node[ground] {};
    
    \draw (8.0, 6.5) -- (MO1.S);
    \draw (MO1.D) -- (MO2.D);
    \draw (MO2.S) -- (8.0, 4.0);

    \draw (6.2, 5.75) -- (MO1.G);
    \draw (6.2, 4.75) -- (MO2.G);

    \draw (8.0, 2.7) node[vcc] {$V_{DD}$};
    \draw (8.0, 2.0) node[pmos, bulk] (MO3) {};
    \draw (8.0, 0.5) node[nmos, bulk] (MO4) {};
    \draw (8.0, -0.2) node[ground] {};
    
    \draw (8.0, 2.5) -- (MO3.S);
    \draw (MO3.D) -- (MO4.D);
    \draw (MO4.S) -- (8.0, 0.0);

    \draw (6.2, 2.25) -- (MO3.G);
    \draw (6.2, 1.25) -- (MO4.G);

    % 6. Outputs
    \coordinate (OUT_TOP) at (8.0, 5.25);
    \coordinate (OUT_BOT) at (8.0, 1.25);

    \draw (OUT_TOP) to[short, *-o] (9.2, 5.25) node[right, font=\large] {$V_{\mathrm{PMOS, P(N)}}$};
    \draw (OUT_BOT) to[short, *-o] (9.2, 1.25) node[right, font=\large] {$V_{\mathrm{NMOS, P(N)}}$};

    % 7. Delay Lines
    \draw (8.5, 5.25) to[short, * - ] (8.5, 3.5) -- (7.2, 3.5);
    \draw (7.2, 3.5) to[buffer] (5.4, 3.5) -- (2.5, 3.5) -- (2.5, 1.0) -- (M5.G);
    
    \draw[dashed, thick] (5.2, 3.0) rectangle (7.4, 4.0);
    \draw[->, >=latex, ultra thick, red] (5.6, 2.7) -- (7.0, 4.3);

    \draw (8.8, 1.25) to[short, * - ] (8.8, 3.0) -- (7.2, 3.0);
    \draw (7.2, 3.0) to[buffer] (5.4, 3.0) -- (2.3, 3.0) -- (2.3, 6.0) -- (M2.G);

    \draw[dashed, thick] (5.2, 2.0) rectangle (7.4, 2.9);
    \draw[->, >=latex, ultra thick, red] (5.6, 1.7) -- (7.0, 3.2);

    % 8. Waveforms
    \begin{scope}[shift={(10.5, 0.0)}]
        \draw[thick] (0.0, 5.0) -- (0.8, 5.0) -- (0.8, 4.2) -- (1.6, 4.2) -- (1.6, 5.0) -- (2.4, 5.0);
        \draw[thick] (0.0, 2.0) -- (1.2, 2.0) -- (1.2, 1.2) -- (2.0, 1.2) -- (2.0, 2.0) -- (2.4, 2.0);
        
        \draw[dashed, blue] (0.8, 5.3) -- (0.8, 0.8);
        \draw[dashed, blue] (1.2, 5.3) -- (1.2, 0.8);
        
        \draw[<->, >=latex, thick] (0.8, 3.1) -- (1.2, 3.1);
        \node[right, font=\large] at (1.3, 3.1) {$\sim$6.5ns};
    \end{scope}

\end{tikzpicture}

\end{document}
"""

encoded_latex = urllib.parse.quote(latex_code)
url = f"https://latexonline.cc/compile?text={encoded_latex}"

try:
    response = requests.get(url, timeout=60)
    print("STATUS CODE:", response.status_code)
    print("RESPONSE BODY:")
    print(response.text)
except Exception as e:
    print("ERROR:", e)
