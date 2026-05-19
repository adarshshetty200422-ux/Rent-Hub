from jinja2 import Template
t = Template('<div {{ \'style="width: %.1f%%;"\' | format(((rating or 0.0)/5)*100) | safe }}></div>')
print(t.render(rating=4.0))
