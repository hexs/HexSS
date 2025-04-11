import re


def latex_to_normal(y):
    m = re.match(r'^\\left\((.*)\\right\)(.*)$', y)
    if m:
        y = m.group(1) + m.group(2)

    normal_has_left = ('\\left' in y)

    y = re.sub(r'\\cos', 'cos', y)
    y = re.sub(r'\\left\(', '(', y)
    y = re.sub(r'\\right\)', ')', y)
    y = re.sub(r'\\left', '', y)
    y = re.sub(r'\\right', '', y)
    y = re.sub(r'\\e', 'e', y)
    y = re.sub(r'e\{([^}]*)\}', r'e^(\1)', y)
    y = re.sub(r'\^{([^}]*)}', r'^(\1)', y)
    y = re.sub(r'\^([^\(])', r'^(\1)', y)

    def frac_repl(m):
        num = m.group(1)
        den = m.group(2)

        if re.search(r'[+\-]', den) and not (den.startswith('(') and den.endswith(')')):
            den = f'({den})'
        return f'({num}/{den})'

    y = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', frac_repl, y)
    y = re.sub(r'cos\s+([a-zA-Z0-9]+)', r'cos(\1)', y)
    if normal_has_left:
        y = re.sub(r'\)([a-zA-Z0-9])', r')*\1', y)

    return y


def latex_to_python(y):
    norm = latex_to_normal(y)
    norm = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', norm)
    norm = re.sub(r'(\d)(\()', r'\1*\2', norm)
    norm = re.sub(r'(\))([a-zA-Z])', r'\1*\2', norm)
    norm = re.sub(r'\bcos\(', 'math.cos(', norm)
    norm = re.sub(r'\be\^\(([^)]*)\)', r'math.pow(math.e, \1)', norm)
    norm = re.sub(r'\*', ' * ', norm)
    norm = re.sub(r'\/', ' / ', norm)
    norm = re.sub(r'\+', ' + ', norm)
    norm = re.sub(r'\-', ' - ', norm)
    norm = re.sub(r'\s+', ' ', norm)
    norm = re.sub(r'-\s+([a-zA-Z(])', r'-\1', norm)

    return norm.strip()


if __name__ == '__main__':
    from hexss.constants.terminal_color import *

    # Test cases
    latex_list = [
        r'2\cos\left(100x+30\right)',
        r'10e^{x}+\cos x',
        r'\frac{1}{2}x',
        r'\frac{1}{1+e^{-x}}',
        r'\frac{1}{1+e^{-\left(x-a\right)}}',
        r'\left(\frac{1}{1+e^{-\left(x-a\right)}}\right)b',
    ]
    l2n_answer_list = [
        '2cos(100x+30)',
        '10e^(x)+cos(x)',
        '(1/2)x',
        '(1/(1+e^(-x)))',
        '(1/(1+e^(-(x-a))))',
        '(1/(1+e^(-(x-a))))*b',
    ]
    l2p_answer_list = [
        '2 * math.cos(100 * x + 30)',
        '10 * math.pow(math.e, x) + math.cos(x)',
        '(1 / 2) * x',
        '(1 / (1 + math.pow(math.e, -x)))',
        '(1 / (1 + math.pow(math.e, -(x - a))))',
        '(1 / (1 + math.pow(math.e, -(x - a)))) * b',
    ]

    print(f'\n{BLUE}Test latex_to_normal functions{END}\n')
    for y, answer in zip(latex_list, l2n_answer_list):
        result = latex_to_normal(y)
        print(f'y      = {y}')
        print(f'answer = {answer}')
        print(f'y_l2n  = {result}')
        if result != answer:
            print(f'{RED}Wrong{END}')
        else:
            print(f'{GREEN}Correct{END}')
        print()

    print(f'\n{BLUE}Test latex_to_python functions{END}\n')
    for y, answer in zip(latex_list, l2p_answer_list):
        result = latex_to_python(y)
        print(f'y      = {y}')
        print(f'answer = {answer}')
        print('y_l2p  =', result)
        if result != answer:
            print(f'{RED}Wrong{END}')
        else:
            print(f'{GREEN}Correct{END}')
        print()
