# H1 Heading
## H2 Heading
### H3 Heading

Setext Heading
==============

Subheading
----------

日本語の中で**太字**を使う。
日本語の中で*斜体*を使う。
日本語の中で__underscore太字__も使う。
日本語の中で_underscore italic_も使う。
句読点の直前に**強調**、直後に*斜体*。
複合装飾の例: ***bold italic*** / **_bold italic_** / ~~***strike bold italic***~~
識別子の例: foo_bar_baz は通常テキストのままでいてほしい。
エスケープの例: \*\*not bold\*\* / \_not italic\_ / \~\~not strike\~\~
インラインコード: `run-20260307-01`
backtick を含む code span: ``code with `backtick` inside``

Bare URL: https://example.com/path_(demo)?a=1&b=2#frag
Markdown link: [Example Docs](https://example.com/docs)
Autolink: <https://example.com/autolink>
Slack-style link: <https://example.com/slack|Slack Style>
Mail link: <mailto:test@example.com|test@example.com>
Reference style link: [Reference Style][ref1]
Image syntax: ![Alt text](https://example.com/image.png)

[ref1]: https://example.com/reference

- dash item
* star item
+ plus item
- [ ] task unchecked
- [x] task checked
1. ordered first
3. ordered starts at three
   1. nested number
   2. nested number two
      - nested bullet
- long item first line
  continuation line under the same bullet

> single quote line 1
> single quote line 2
>
> - quoted bullet
> 1. quoted number
>> nested quote
>>> third-level quote

Line with backslash hard break\
Next line after slash break

---

***

___

```python
def greet(name):
    print(f"Hello, {name}")
```

```
a | b | c
--- | --- | ---
inside code fence, not a table
```

~~~sql
select *
from users
where id = 1;
~~~

| Name | Status | Notes |
|---|---|---|
| Amy | **OK** | `run-1` |
| Chloe | *Check* | [Docs](https://example.com) |
| Gal | ~~Hold~~ | <https://example.com|Link> |

No outer pipes table header | Col2 | Col3
row1 | A | B
row2 | C |

### Heading inline table Header A | Header B
value A | value B

| Expr | Meaning |
|---|---|
| `a|b` | pipe in code |
| A \| B | escaped pipe |

Entities: A &gt; B &amp; C &lt; D
Raw HTML-like tag: <div class="note">hello</div>
Unknown angle token: <foo>
Full-width brackets: ＜bar＞

Math-ish inline: $x^2 + y^2 = z^2$
Math-ish block:
$$
E = mc^2
$$

> [!NOTE]
> This is an admonition-like block.

<!-- html comment should probably not render as-is -->

<details>
<summary>Details tag</summary>
Hidden-ish text
</details>

```mermaid
graph TD
  A --> B
```
