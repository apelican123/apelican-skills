# 公众号 AppID、AppSecret 和 IP 白名单

这份说明按 2026 年微信官方文档的**当前入口**写。旧教程里的「公众平台 → 开发 → 基本配置」已经迁走。

官方说明：

- 开发配置迁移：https://developers.weixin.qq.com/doc/subscription/guide/dev/migration.html
- 启用 AppSecret：https://developers.weixin.qq.com/doc/oplatform/developers/product/subscription_service/appid.html
- 草稿接口：https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html

页面文案以后若改名，以你打开的页面为准，但「开发者平台 → 我的业务 → 公众号 → 开发密钥」这条主路径应当还在。

## 先分清三个网站

| 网站 | 地址 | 这个技能要不要去 |
| --- | --- | --- |
| 微信公众平台 | https://mp.weixin.qq.com/ | 要。用来注册公众号、完成实名/认证、最后预览草稿 |
| 微信开发者平台 | https://developers.weixin.qq.com/platform/ | **要。AppID、AppSecret、IP 白名单都在这里取** |
| 微信开放平台 | https://open.weixin.qq.com/ | **不要为了本技能去注册。** 那是移动应用、网站应用、第三方平台用的另一套 AppID |

有人会把「开放平台」和「开发者平台」看成一回事。不是。把开放平台里移动应用的 AppID 填进 `.env`，草稿接口会报凭证不合法。

## 第一步：公众号本身要能启用密钥

1. 打开 https://mp.weixin.qq.com/ ，微信扫码登录你的公众号。
2. 个人主体：到「账号详情 → 主体信息」，确认已经显示管理员姓名。没有就到「设置与开发 → 人员设置 → 管理员信息」完成实名。
3. 企业 / 组织主体：到「账号详情 → 认证情况」。未认证时，启用 AppSecret 会被挡下来，需要先申请微信认证。
4. 确认登录的微信是管理员，或已经是该公众号的开发者。运营者权限不够。

## 第二步：登录微信开发者平台

1. 打开 https://developers.weixin.qq.com/platform/
2. 用**管理员或开发者**的微信扫码。
3. 登录后看「我的业务」。
4. 往下滑，找到 **公众号**（不要点成小程序、小游戏、移动应用）。
5. 点进你的那个公众号。

如果这里一个公众号都没有：当前微信号不是任何公众号的管理员/开发者。回到公众平台处理身份，不要在开放平台新建应用凑数。

## 第三步：查看 AppID

1. 进入公众号后，打开 **基础信息**（有的页面分组在「能力」附近，点进去能看到开发者 ID）。
2. 复制 **开发者 ID（AppID）**。一般以 `wx` 开头。
3. 把它贴到技能目录 `.env` 的 `WECHAT_APP_ID=` 后面。

AppID 不是秘密到不能出现在自己的配置里，但也不要发到公开仓库。

## 第四步：启用或重置 AppSecret

1. 在同一页进入 **开发密钥**。
2. 若尚未启用，点启用。按页面完成管理员确认。
3. **密钥只展示这一次。** 官方明确：平台不保存、不回显 AppSecret。关掉页面就看不见了。
4. **点启用之前**，先在电脑打开一个空白记事本（或已经建好的 `.env`），密钥一出来立刻粘贴进去再关页。
5. 立刻写到 `.env` 的 `WECHAT_APP_SECRET=` 后面，本地保存。
6. 以后忘记了只能点**重置**。重置会使旧密钥立即失效，所有还在用旧密钥的脚本都会挂。

启用时若提示「尚未完成实名」或「尚未完成主体认证」，回到第一步，不要反复点启用。

## 第五步：加入 IP 白名单

调用 `api.weixin.qq.com` 的机器，出口公网 IPv4 必须在白名单里，否则返回 `40164 invalid ip`。

1. 在**将要运行 wenyan 的那台电脑**上查当前公网 IPv4。

   bash：

   ```bash
   curl -4 https://ifconfig.me/ip
   ```

   PowerShell：

   ```powershell
   Invoke-RestMethod -Uri https://ifconfig.me/ip
   ```

2. 你会得到类似 `203.0.113.10` 的四段数字。
3. 回到开发者平台同一页的 **API IP 白名单**，把这个地址加进去。
4. 不要填 `127.0.0.1`。那是本机自己，微信的服务器看不到它。
5. 如果你开了系统代理 / VPN，白名单里要填**实际访问微信接口的出口 IP**。查到的 IP 和真实出口不一致时，以微信报错里返回的 IP 为准。

家用宽带 IP 可能会变。变了就再查一次、再加一次。频繁变动时，wenyan 提供把上传放到固定 IP 服务器上的 server 模式，见 https://github.com/caol64/wenyan-cli ；本技能默认本机直连，不强制上服务器。

## 第六步：自检，不要把密钥贴回来

在技能根目录：

```bash
source ./scripts/setup.sh
```

```powershell
.\scripts\setup.ps1
```

看到「已加载」即可。脚本不应打印 AppSecret。若你把密钥发到了聊天或截图，去开发密钥页重置，并更新 `.env`。

## 第七步：接口权限（可选但建议看一眼）

开发者平台 → 我的业务 → 公众号 → **接口管理 → 接口权限与额度**。

确认与草稿、素材相关的接口不是「未授权」。官方文档写明：新增草稿接口对**公众号**和**服务号**都可用。若这里显示未授权，先不要怀疑脚本，先看账号类型和权限页。

## 完成后台预览时回公众平台

密钥在开发者平台取；草稿列表在 https://mp.weixin.qq.com/ 。找不到草稿箱时看 [mp-publish.md](mp-publish.md)。两个后台不要用混。
