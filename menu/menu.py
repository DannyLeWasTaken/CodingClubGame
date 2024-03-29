import pygame as pg
from textwrap import wrap
import dialog.dialog as dialog
import battle.battle as battle
import stats.stats as stats
import mapScreen.mapScreen as mapScreen
import math
import copy
import esper
import online.readWrite as serverRW
import immutable.consts as consts
import save.save as save

def printScr(text: str, posx: float, posy: float, colour: pg.Color, font: pg.font.Font, screen: pg.Surface):
    """
    Render text at (posx,posy) of screen, using font in provided colour.
    """
    render = font.render(text, True, colour)
    rect = render.get_rect()
    rect.center = posx, posy
    rect.left = posx
    screen.blit(render, rect)

def drawPortrait(posx, posy, screen):
    """
    Draw the given character portrait centered at *posx*,*posy*. Currently draws a 128x128 white square for testing purposes.
    """
    pg.draw.rect(screen, (255,255,255), pg.Rect(posx-64,posy-64,128,128))

def printWrapped(text: str, width: int, lineSpacing: int, posx: float, posy: float, colour: pg.Color, font: pg.font.Font, screen: pg.Surface):
    """
    Render text wrapped at width at (posx,posy) of screen, using font in provided colour.
    """
    wrapped = wrap(text, width=width)
        
    for i in range(0, len(wrapped)):
        printScr("".join(wrapped[i]), posx, posy+lineSpacing*i, (255,255,255), font, screen)

def drawMenuBox(screen, left, top, length, height):
    pg.draw.rect(screen, consts.menuBackgroundColour, pg.Rect(left, top, length, height))
    pg.draw.rect(screen, (255,255,255), pg.Rect(left, top, length, height),4)

def drawHorizontalBar(screen, left, top, length, height, color, value, max):
    pg.draw.rect(screen, (0,0,0), pg.Rect(left, top, length, height))
    pg.draw.rect(screen, color, pg.Rect(left, top, length*value/max, height))

def drawVerticalBar(screen, left, top, length, height, color, value, max):
    pg.draw.rect(screen, (0,0,0), pg.Rect(left, top, length, height))
    pg.draw.rect(screen, color, pg.Rect(left, top, length, height*value/max))

class MenuProcessor(esper.Processor):
    def process(self):
        inputs = self.world.get_component(mapScreen.Input)[0][1].buttons
        screen = self.world.get_component(mapScreen.Consts)[0][1].screen
        for i, menu in self.world.get_component(Menu):
            if menu.active:
                menu.Update(screen, self.world, inputs)

class Menu:
    def __init__(self, items, options, start):
        """
        General-purpose class that holds a dict of MenuItems
        """
        self.startVisible = {k:v.visible for k,v in items.items()}
        self.items = items
        self.options = options
        self.start = start
        self.current = start
        self.active = False
        self.holdingMenu = True
        self.closable = False
    def Activate(self):
        for key in self.items.keys():
            self.items[key].visible = self.startVisible[key]
        self.active = True
        self.options[self.current].Activate()
        self.holdingMenu = True
    def Deactivate(self):
        self.current = self.start
        self.active = False
        self.holdingMenu = True
    def Update(self, screen, world, inputs):
        if not(self.holdingMenu) and inputs["menu"] and self.closable:
            self.Deactivate()
            world.get_component(mapScreen.PlayerMove)[0][1].Sync()
            return -1
        if not(inputs["menu"]):
            self.holdingMenu = False
        
        for item in self.items.values():
            if item.visible:
                item.draw(screen, world)
        self.options[self.current].draw(screen)
        result = self.options[self.current].Update(screen, world, inputs)
        self.options[self.current].oldInputs = copy.deepcopy(inputs)
        if result == -1:
            return -1
        elif result == -2:
            self.Deactivate()
        else:
            print(result)
            self.options[self.current].Deactivate()
            self.current = result
            self.options[self.current].Activate()
            return -1

def ClassMenu():
    classMenu = Menu(
        {
            "Background Layer 0":BackgroundMenu(True),
            "ClassChoices":ClassChoiceMenu(True,0),
            "ConfirmationWindow":OptionsMenu(120, 100, 400, 240, ["Are you sure?","This choice is permanent.","Don't sweat it too much, though,","all of them will be usable."], False)
        },
        {
            "ClassOptions":MenuOptionsHandler(["englishConfirm", "scienceConfirm", "mathConfirm", "artConfirm", "historyConfirm", "psychologyConfirm", "languagesConfirm"], True,
                                             8,88,0,45)
        },
        "ClassOptions"
    )

    for className in ["english", "science", "math", "art", "history", "psychology", "languages"]:
        classMenu.options[f"{className}Confirm"] = MenuChangerHandler({"ConfirmationWindow":True}, classMenu, f"{className}FinalCheck")
        classMenu.options[f"{className}Back"] = MenuChangerHandler({"ConfirmationWindow":False}, classMenu, "ClassOptions")
        classMenu.options[f"{className}FinalCheck"] = MenuOptionsHandler([className], f"{className}Back", 500, 500, 0, 0)
        classMenu.options[className] = ClassChoiceHandler(className,0,-2)
    
    return classMenu

def LoginMenu():
    loginMenu = Menu(
        {
            "Background Layer":BackgroundMenu(True),
            "Save Files":SaveFilesMenu(False),
            "New/Load":OptionsMenu(520, 0, 120, 480, ["New", "Load"], False)
        },
        dict(),
        "Login"
    )
    loginMenu.options = {
            "Login":LoginHandler("Login Done"),
            "Login Done":MenuChangerHandler({"Save Files":True, "New/Load":False}, loginMenu, "File Choice"),
            "File Choice":MenuOptionsHandler(["File0","File1","File2","File3","File4"], "File Choice", 0, 48, 0, 96)
        }
    for i in range(5):
        loginMenu.options[f"File{i}"] = MenuChangerHandler({"New/Load":True}, loginMenu, f"FileOptions{i}")
        loginMenu.options[f"FileOptions{i}"] = MenuOptionsHandler([f"New{i}", f"Load{i}"], "Login Done", 520, 24, 0, 48)
        loginMenu.options[f"New{i}"] = NewFileHandler(i, -2)
        loginMenu.options[f"Load{i}"] = LoadFileHandler(i, -2)

    
    return loginMenu

def PauseMenu(world):
    characters = world.get_component(dialog.PlayerData)[0][1].characters
    pauseMenu = Menu(
    {
        "Background Layer 0":BackgroundMenu(True),
        "Portrait 0":PortraitMenu(2,2,True,0),
        "Portrait 1":PortraitMenu(2,144,True,1),
        "Portrait 2":PortraitMenu(2,286,True,2),
        "SharedStatsViewer":SharedStatsMenu(2,426,True),
        "OptionsSidebar":OptionsMenu(452,2,188,474,["View Stats", "Equipment", "Inventory", "Key Items", "Change Spells", "Change Order", "Save", "Quit to Title"], True),
        "Background Layer 1":BackgroundMenu(False),
        "Stats 0":StatsMenu(False,0),
        "Stats 1":StatsMenu(False,1),
        "Stats 2":StatsMenu(False,2),
        "Spells 0":SpellMenu(False,0),
        "Spells 1":SpellMenu(False,1),
        "Spells 2":SpellMenu(False,2),
        "SaveSlots":SaveFilesMenu(False)
    },
    {
        "OptionsSidebar":MenuOptionsHandler(["Stats","Equipment","Inventory","Key Items","Spells","Order","Save","Quit"],"OptionsSidebar",
                                                448,22,0,48),
        "Stats":MenuOptionsHandler([f"Stats{i}" for i in range(len(characters))],"OptionsSidebar",
                                       8,72,0,144),
        "Equipment":MenuOptionsHandler([f"Equipment{i}" for i in range(len(characters))],"OptionsSidebar",
                                       8,72,0,144),
        "Inventory":MenuOptionsHandler([],"OptionsSidebar",
                                       8,72,0,144),
        "KeyItems":MenuOptionsHandler([],"OptionsSidebar",
                                       8,72,0,144),
        "Spells":MenuOptionsHandler([f"Spells{i}" for i in range(len(characters))],"OptionsSidebar",
                                       8,72,0,144),
        "Order":MenuOptionsHandler([f"Order{i}" for i in range(len(characters))],"OptionsSidebar",
                                       8,72,0,144)
    },
    "OptionsSidebar"
    )
    
    pauseMenu.closable = True

    pauseMenu.options["Save"] = MenuChangerHandler({"Background Layer 1":True,"SaveSlots":True},pauseMenu,"SaveSlots")
    pauseMenu.options["SaveSlots"] = MenuOptionsHandler(["File0","File1","File2","File3","File4"], "SaveBack", 0, 48, 0, 96)
    pauseMenu.options["SaveBack"] = MenuChangerHandler({"Background Layer 1":False,"SaveSlots":False},pauseMenu,"OptionsSidebar")

    
    for i in range(5):
        pauseMenu.options[f"File{i}"] = SaveGameHandler(i, "SaveBack")
    
    for i in range(len(characters)):
        pauseMenu.options[f"Order{i}"] = MenuOptionsHandler([f"Order{i}|{j}" for j in range(len(characters))],"Order",
                                       8,72,0,144)
        for j in range(len(characters)):
            pauseMenu.options[f"Order{i}|{j}"] = MenuSwapHandler(i,j,"OptionsSidebar")

    for i in range(len(characters)):
        pauseMenu.options[f"Spells{i}"] = MenuChangerHandler({"Background Layer 1":True,f"Spells {i}":True},pauseMenu,f"SpellList{i}")
        pauseMenu.options[f"SpellList{i}"] = MenuToggleListHandler(characters[i].spellNames,f"SpellsBack{i}",
                                                                  8,16,0,56,maxToggle=4)
        pauseMenu.options[f"SpellsBack{i}"] = MenuChangerHandler({"Background Layer 1":False,f"Spells {i}":False},pauseMenu,f"OptionsSidebar")
        
        pauseMenu.options[f"Stats{i}"] = MenuChangerHandler({"Background Layer 1":True,f"Stats {i}":True},pauseMenu,f"EV{i}")
        pauseMenu.options[f"EV{i}"] = MenuOptionsHandler([f"EVmaxHP{i}",f"EVphysAtk{i}",f"EVmagiAtk{i}",f"EVphysDef{i}",f"EVmagiDef{i}"],f"StatsBack{i}",
                                                         0,212,0,48)
        pauseMenu.options[f"StatsBack{i}"] = MenuChangerHandler({"Background Layer 1":False,f"Stats {i}":False},pauseMenu,"OptionsSidebar")
        for stat in ["maxHP","physAtk","physDef","magiAtk","magiDef"]:
            pauseMenu.options[f"EV{stat}{i}"] = MenuEVBoostHandler(stat, i, f"EV{i}", f"EV{i}")
        
    
    return pauseMenu

class MenuHandler:
    """
    Base class for active menu elements.
    """
    def __init__(self, next, previous):
        self.next = next
        self.previous = previous
        self.active = False
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        pass

class LoginHandler(MenuHandler):
    """
    Handles the login process.
    When finished, creates a Credentials entity.
    """
    def __init__(self, next):
        self.next = next
        self.stage = 0
        self.username = None
        self.password = None
        self.typed = ""
        self.font = pg.font.SysFont("Courier", 16)
    def Activate(self):
        pg.key.start_text_input()
        self.active = True
        self.stage = 0
        self.username = None
        self.password = None
        self.typed = ""
    def Deactivate(self):
        pg.key.stop_text_input()
        self.active = False
    def draw(self, screen):
        printScr("Login:", 16, 16, (255,255,255), self.font, screen)
        if self.stage == 0:
            printScr("Username:", 16, 64, (255,255,255), self.font, screen)
            printScr(self.typed+"_", 16, 80, (255,255,255), self.font, screen)
        elif self.stage == 1:
            printScr("Password:", 16, 64, (255,255,255), self.font, screen)
            printScr("*"*len(self.typed)+"_", 16, 80, (255,255,255), self.font, screen)
        else:
            printScr("Verifying...", 16, 64, (255,255,255), self.font, screen)

        printScr("Controls:",16,120,(255,255,255),self.font,screen)
        printScr("WASD or ARROW KEYS: Move, navigate menus",16,140,(255,255,255),self.font,screen)
        printScr("Z or RETURN: Confirm",16,156,(255,255,255),self.font,screen)
        printScr("Z or RETURN while walking at someone/thing: Interact",16,172,(255,255,255),self.font,screen)
        printScr("X or LEFT SHIFT: Cancel, skip text",16,188,(255,255,255),self.font,screen)
        printScr("C or ESCAPE: Pause",16,204,(255,255,255),self.font,screen)
    def Update(self, screen, world, inputs):
        if self.stage == 2:
            self.stage += 1
        elif self.stage == 3:
            print("Wake up server:", serverRW.wakeUpServer())
            if serverRW.getData(self.username, self.password) == -1:
                print("Invalid")
                self.typed = ""
                self.stage = 0
            else:
                print("Valid")
                world.create_entity(serverRW.Credentials(self.username, self.password))
                return self.next
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_RETURN:
                    if self.stage == 0:
                        self.username = self.typed
                        self.typed = ""
                        self.stage += 1
                    elif self.stage == 1:
                        self.password = self.typed
                        self.typed = ""
                        self.stage += 1
                    
                elif event.key == pg.K_BACKSPACE:
                    self.typed = self.typed[:-1]
            elif event.type == pg.TEXTINPUT:
                self.typed += event.text
        return -1

class SaveGameHandler(MenuHandler):
    """
    Handles saving file.
    """
    def __init__(self, slot, next):
        self.slot = slot
        self.next = next
        self.font = pg.font.SysFont("Courier", 16)
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        pass
    def Update(self, screen, world, inputs):
        mapName = world.get_component(mapScreen.TileMap)[0][1].name
        posx = int(world.get_components(mapScreen.PlayerMove, mapScreen.Position)[0][1][1].posx//32)
        posy = int(world.get_components(mapScreen.PlayerMove, mapScreen.Position)[0][1][1].posy//32)
        print(posx,posy)
        playerData = world.get_component(dialog.PlayerData)[0][1]
        saveGame = save.SaveData(mapName, posx, posy, playerData)
        creds = world.get_component(serverRW.Credentials)[0][1]
        pickled = serverRW.prepareData(saveGame)
        drawMenuBox(screen, 280, 220, 80, 40)
        printScr("Saving...", 296, 236, (255,255,255), self.font, screen)
        serverRW.saveData(creds.username, creds.password, "ProgrammingClubRPG", f"File{self.slot}", pickled)
        return self.next

class NewFileHandler(MenuHandler):
    """
    Handles creating a new file and booting it up.
    """
    def __init__(self, fileSlot, next):
        self.fileSlot = fileSlot
        self.next = next
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        pass
    def Update(self, screen, world, inputs):
        save.SaveData.newGame(world)
        return self.next

class LoadFileHandler(MenuHandler):
    """
    Handles loading save data.
    """
    def __init__(self, fileSlot, next):
        self.fileSlot = fileSlot
        self.next = next
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        pass
    def Update(self, screen, world, inputs):
        creds = world.get_component(serverRW.Credentials)[0][1]
        saveData = serverRW.getData(creds.username, creds.password)["saves"]["ProgrammingClubRPG"][f"File{self.fileSlot}"]
        saveObj = serverRW.decodePickle(saveData)
        saveObj.startWorld(world)
        return self.next

class ClassChoiceHandler(MenuHandler):
    """
    Handles choosing/changing class.
    """
    def __init__(self, className, id, next):
        self.className = className
        self.id = id
        self.next = next
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        pass
    def Update(self, screen, world, inputs):
        playerData = world.get_component(dialog.PlayerData)[0][1]
        character = playerData.characters[self.id]
        with open("stats/classStats.txt") as classData:
            classDict = stats.readClassStats(classData.read())
        character.baseStats.ivs = classDict[self.className]
        character.className = self.className.lower()
        character.playerClass = self.className.title()
        character.baseStats.calculate()
        character.calculate()
        character.hp = min(character.hp, character.baseStats.finalStats["maxHP"])
        spellsPerClass = consts.spellsPerClass
        character.spellNames = [[spellsPerClass[self.className][0],True]]
        playerData.mainClass = self.className.lower()
        return self.next

class MenuEVBoostHandler(MenuHandler):
    """
    Handles boosting an EV.
    """
    def __init__(self, stat, id, next, previous):
        self.stat = stat
        self.id = id
        self.next = next
        self.previous = previous
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        pass
    def Update(self, screen, world, inputs):
        character = world.get_component(dialog.PlayerData)[0][1].characters[self.id]
        if character.skillPoints > 0 and character.baseStats.evs[self.stat] < 8:
            character.baseStats.setEv(self.stat, character.baseStats.evs[self.stat]+1)
            character.skillPoints -= 1
            character.calculate()
        return self.next

class MenuChangerHandler(MenuHandler):
    """
    Shows/hides menu displays, then goes to the next.
    """
    def __init__(self, displayDict, parentMenu, next):
        self.active = False
        self.displayDict = displayDict
        self.parentMenu = parentMenu
        self.next = next
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def Update(self, screen, world, inputs):
        for key, value in self.displayDict.items():
            self.parentMenu.items[key].visible = value
        return self.next

class MenuSwapHandler(MenuHandler):
    """
    Swaps two party positions, then goes to the next.
    """
    def __init__(self, pos0, pos1, next):
        self.active = False
        self.pos0 = pos0
        self.pos1 = pos1
        self.next = next
    def Activate(self):
        self.active = True
    def Deactivate(self):
        self.active = False
    def Update(self, screen, world, inputs):
        partyList = world.get_component(dialog.PlayerData)[0][1].characters
        temp = partyList[self.pos0]
        partyList[self.pos0] = partyList[self.pos1]
        partyList[self.pos1] = temp
        return self.next

class MenuOptionsHandler(MenuHandler):
    """
    Holds a list of selectable options, and handles input to it including confirm/cancel.
    """
    def __init__(self, optionList, previous, posx, posy, shiftx, shifty, mode="vertical"):
        self.oldInputs = {
            "confirm":True,
            "cancel":True,
            "menu":True,
            "left":True,
            "right":True,
            "up":True,
            "down":True
        }
        self.selected = 0
        self.optionList = optionList
        self.optionCount = len(optionList)
        self.previous = previous
        self.posx = posx
        self.posy = posy
        self.shiftx = shiftx
        self.shifty = shifty
        self.mode = mode
        self.conditions = [dialog.Condition() for i in range(self.optionCount)]
        if self.mode == "vertical":
            self.plusOption = "down"
            self.minusOption = "up"
        else:
            self.plusOption = "right"
            self.minusOption = "left"
        self.active = False
        self.pointer = pg.image.load("assets/art/ui/menus/pointer.png").convert_alpha()
    def Conditions(optionList, previous, posx, posy, shiftx, shifty, conditions, mode="vertical"):
        handler = MenuOptionsHandler(optionList, previous, posx, posy, shiftx, shifty, mode)
        handler.conditions = conditions
        return handler
    def Activate(self):
        self.selected = 0
        self.active = True
        self.oldInputs = {
            "confirm":True,
            "cancel":True,
            "menu":True,
            "left":True,
            "right":True,
            "up":True,
            "down":True
        }
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        """
        Draws a pointer at the location of the current option.
        """
        if self.optionList:
            rect = self.pointer.get_rect()
            rect.center = self.posx + self.selected*self.shiftx, self.posy + self.selected*self.shifty
            screen.blit(self.pointer, rect)
    def Update(self, screen, world, inputs):
        if len(world.get_component(dialog.PlayerData)) > 0:
            playerData = world.get_component(dialog.PlayerData)[0][1]
        else:
            playerData = dialog.PlayerData([],[],[],[],battle.SharedStats(0,0,0,0),"none")
        if self.oldInputs["confirm"] == False and inputs["confirm"] and self.conditions[self.selected].verify("", playerData):
            # Return chosen MenuOptionsHandler name
            print("Confirm")
            return self.optionList[self.selected]
        if self.oldInputs["cancel"] == False and inputs["cancel"]:
            # Return previous MenuOptionsHandler name
            print("Cancel")
            return self.previous
        if self.oldInputs[self.plusOption] == False and inputs[self.plusOption]:
            print("+")
            self.selected = (self.selected + 1) % self.optionCount
        if self.oldInputs[self.minusOption] == False and inputs[self.minusOption]:
            print("-")
            self.selected = (self.selected - 1) % self.optionCount
        return -1

        
class MenuToggleListHandler(MenuHandler):
    """
    Holds a list of toggleable options, and handles input to it including confirm/cancel.
    Individual options have to be in the form (optionName, on/off)
    maxToggle controls maximum number active at once.
    """
    def __init__(self, optionList, previous, posx, posy, shiftx, shifty, maxToggle=100, mode="vertical"):
        self.oldInputs = {
            "confirm":True,
            "cancel":True,
            "menu":True,
            "left":True,
            "right":True,
            "up":True,
            "down":True
        }
        self.selected = 0
        self.optionList = optionList
        self.optionCount = len(optionList)
        self.previous = previous
        self.posx = posx
        self.posy = posy
        self.shiftx = shiftx
        self.shifty = shifty
        self.maxToggle = maxToggle
        self.mode = mode
        if self.mode == "vertical":
            self.plusOption = "down"
            self.minusOption = "up"
        else:
            self.plusOption = "right"
            self.minusOption = "left"
        self.active = False
        self.pointer = pg.image.load("assets/art/ui/menus/pointer.png").convert_alpha()
    def Activate(self):
        self.selected = 0
        self.active = True
        self.oldInputs = {
            "confirm":True,
            "cancel":True,
            "menu":True,
            "left":True,
            "right":True,
            "up":True,
            "down":True
        }
    def Deactivate(self):
        self.active = False
    def draw(self, screen):
        """
        Draws a pointer at the location of the current option.
        """
        if self.optionList:
            rect = self.pointer.get_rect()
            rect.center = self.posx + self.selected*self.shiftx, self.posy + self.selected*self.shifty
            screen.blit(self.pointer, rect)
    def Update(self, screen, world, inputs):
        if self.optionList:
            totalToggled = sum(1 for i, j in self.optionList if j)
            if self.oldInputs["confirm"] == False and inputs["confirm"]:
                # Return chosen MenuOptionsHandler name
                print("Confirm")
                if self.optionList[self.selected][1]:
                    self.optionList[self.selected][1] = False
                else:
                    if totalToggled < self.maxToggle:
                        self.optionList[self.selected][1] = True
            if self.oldInputs["cancel"] == False and inputs["cancel"]:
                # Return previous MenuOptionsHandler name
                print("Cancel")
                return self.previous
            if self.oldInputs[self.plusOption] == False and inputs[self.plusOption]:
                print("+")
                self.selected = (self.selected + 1) % self.optionCount
            if self.oldInputs[self.minusOption] == False and inputs[self.minusOption]:
                print("-")
                self.selected = (self.selected - 1) % self.optionCount
            return -1
        else:
            return self.previous

        

class MenuItem:
    def __init__(self, posx, posy, visible):
        self.posx = posx
        self.posy = posy
        self.visible = visible
    def draw(self, screen, world):
        pass
    def Update(self, screen, world, inputs):
        pass

class SpellMenu(MenuItem):
    def __init__(self, visible, index):
        self.visible = visible
        self.font = pg.font.SysFont("Courier", 16)
        self.index = index
    def draw(self, screen, world):
        character = world.get_component(dialog.PlayerData)[0][1].characters[self.index]

        spellList = character.spellNames

        for y in range(len(spellList)):
            if spellList[y][1]:
                pg.draw.circle(screen, (255,255,255), (16, 16+y*56), 8)
            printWrapped(spellList[y][0],15,24,32,16+y*56,(255,255,255),self.font,screen)
        
            description = " ".join(battle.spellList[spellList[y][0]].description[1:-1])
            printWrapped(description, 40, 24, 192, 16+y*56, (255,255,255),self.font,screen)

class StatsMenu(MenuItem):
    def __init__(self, visible, index):
        self.visible = visible
        self.font = pg.font.SysFont("Courier", 16)
        self.index = index
    def draw(self, screen, world):
        xpPerLevelUp = consts.xpPerLevelUp
        
        character = world.get_component(dialog.PlayerData)[0][1].characters[self.index]
        hp = character.hp
        hpMax = character.baseStats.finalStats["maxHP"]
        className = character.playerClass

        xp = world.get_component(dialog.PlayerData)[0][1].sharedStats.xp
        level = character.baseStats.level
        toNext = xpPerLevelUp[character.baseStats.level] - xp

        name = character.name
        skillPoints = character.skillPoints

        self.posx = 16
        self.posy = 16
        
        # Draw values
        #  Name
        printScr(name, self.posx+148, self.posy+16, (255,255,255), self.font, screen)
        #  HP
        printScr(f"HP:{hp:4}/{hpMax:4}", self.posx+148, self.posy+36, (255,255,255), self.font, screen)
        drawHorizontalBar(screen, self.posx+280, self.posy+28, 160, 16, (0,255,0), hp, hpMax)
        #  Level
        printScr(f"Level {level:2}", self.posx+148, self.posy+56, (255,255,255), self.font, screen)
        #  XP to next
        if level < 20:
            drawHorizontalBar(screen, self.posx+280, self.posy+48, 160, 16, (0,255,255), xp, xpPerLevelUp[level])
            printScr(f"To next level: {toNext:8}", self.posx+148, self.posy+76, (255,255,255), self.font, screen)
        else:
            drawHorizontalBar(screen, self.posx+280, self.posy+48, 160, 16, (0,255,255), 1, 1)
            printScr(f"MAX LEVEL", self.posx+148, self.posy+76, (255,255,255), self.font, screen)
        #  Class
        printScr(f"Class: {className:10}", self.posx+148, self.posy+96, (255,255,255), self.font, screen)
        printScr(f"Spend Skill Points: {skillPoints:2} left", self.posx+148, self.posy+116, (255,255,255), self.font, screen)

        printScr("Stats without equipment:", self.posx, self.posy+164, (255,255,255), self.font, screen)

        
        for i, skillName in enumerate(["maxHP", "physAtk", "magiAtk", "physDef", "magiDef"]):
            if character.baseStats.evs[skillName] > 7:
                printScr(f"{skillName:8}:{character.baseStats.finalStats[skillName]:4} ({character.baseStats.evs[skillName]:1}/8 EVs)", self.posx, self.posy+196+i*48, (50,255,50), self.font, screen)
            else:
                printScr(f"{skillName:8}:{character.baseStats.finalStats[skillName]:4} ({character.baseStats.evs[skillName]:1}/8 EVs)", self.posx, self.posy+196+i*48, (255,255,255), self.font, screen)

        shortNames = {"maxHP":"HP","physAtk":"PA","physDef":"PD","magiAtk":"MA","magiDef":"MD"}
        
        # Stat Pentagon
        #  Backing Pentagon and inner tickmarks
        pg.draw.polygon(screen, (255,255,255), [(math.cos(math.pi*i*2/5-math.pi/2)*150+448,math.sin(math.pi*i*2/5-math.pi/2)*150+320) for i in range(5)],4)
        pg.draw.polygon(screen, (255,255,255), [(math.cos(math.pi*i*2/5-math.pi/2)*75+448,math.sin(math.pi*i*2/5-math.pi/2)*75+320) for i in range(5)],2)
        maxValue = stats.baseStatCalc(character.baseStats.level, 2, 8)

        finalPoly = []
        
        for i, skillName in enumerate(["maxHP", "physAtk", "physDef", "magiDef", "magiAtk"]):
            pg.draw.line(screen, (255,255,255), [448, 320], [math.cos(math.pi*i*2/5-math.pi/2)*150+448, math.sin(math.pi*i*2/5-math.pi/2)*150+320], 1)
            finalPoly.append([math.cos(math.pi*i*2/5-math.pi/2)*150*character.baseStats.finalStats[skillName]/maxValue+448, math.sin(math.pi*i*2/5-math.pi/2)*150*character.baseStats.finalStats[skillName]/maxValue+320])
            printScr(shortNames[skillName], math.cos(math.pi*i*2/5-math.pi/2)*165+448, math.sin(math.pi*i*2/5-math.pi/2)*165+320, (255,255,255), self.font, screen)
        pg.draw.polygon(screen, (100,100,255), finalPoly)

class ClassChoiceMenu(MenuItem):
    def __init__(self, visible, index):
        self.visible = visible
        self.index = index
        self.font = pg.font.SysFont("Courier", 16)
        self.images = dict()
        for i, className in enumerate(["english", "science", "math", "art", "history", "psychology", "languages"]):
            self.images[className] = pg.image.load(f"assets/art/ui/menus/icon_{className}.png").convert_alpha()

        self.descriptions = {
            "english":"Well-rounded class with a wide variety of skills.",
            "science":"Heavy hitter with strong offensive skills, but has poor survivability.",
            "math":"Defensive class with a focus on protection and redirection.",
            "art":"Physically weak, but can summon a creature to fight for it.",
            "history":"Defensive class with a focus on healing self and allies.",
            "psychology":"Supportive class that has many buffing and debuffing abilities.",
            "languages":"Heavy physical hitter with a variety of complex skills."
        }
        
    def draw(self, screen, world):
        printScr("CHOOSE CLASS", 16, 16, (255,255,255), self.font, screen)
        for i, className in enumerate(["english", "science", "math", "art", "history", "psychology", "languages"]):
            rect = self.images[className].get_rect()
            rect.left = 16 + 45*(i%2)
            rect.top = 56 + 45*i
            screen.blit(self.images[className], rect)
            printWrapped(f"{className.title():10}:", 48, 20, 144, 80+i*45, (255,255,255), self.font, screen)
            printWrapped(f"{self.descriptions[className]}", 36, 20, 256, 80+i*45, (255,255,255), self.font, screen)
            
class SaveFilesMenu(MenuItem):
    def __init__(self, visible):
        self.visible = visible
        self.saveData = None
        self.font = pg.font.SysFont("Courier", 16)
    def draw(self, screen, world):
        if self.saveData is None:
            creds = world.get_component(serverRW.Credentials)[0][1]
            self.saveData = serverRW.getData(creds.username, creds.password)["saves"]["ProgrammingClubRPG"]

        for i, saveSlot in enumerate(self.saveData.keys()):
            drawMenuBox(screen, 0, i*96, 640, 96)
            if self.saveData[saveSlot] is None:
                printScr("EMPTY FILE", 16, i*96+16, (255,255,255), self.font, screen)
            else:
                data = serverRW.decodePickle(self.saveData[saveSlot])
                printScr(f"Party level {data.playerData.characters[0].baseStats.level}",16,i*96+16,(255,255,255),self.font,screen)

class PortraitMenu(MenuItem):
    def __init__(self, posx, posy, visible, index):
        self.posx = posx
        self.posy = posy
        self.visible = visible
        self.font = pg.font.SysFont("Courier", 16)
        # Character party index this menu is tied to
        self.index = index
    def draw(self, screen, world):
        
        xpPerLevelUp = consts.xpPerLevelUp
        
        # Backing
        drawMenuBox(screen, self.posx, self.posy, 550, 144)
        if len(world.get_component(dialog.PlayerData)[0][1].characters) <= self.index:
            return 1

        # Character portrait
        drawPortrait(self.posx+72, self.posy+72, screen)

        # Values
        character = world.get_component(dialog.PlayerData)[0][1].characters[self.index]
        hp = character.hp
        hpMax = character.baseStats.finalStats["maxHP"]
        className = character.playerClass

        xp = world.get_component(dialog.PlayerData)[0][1].sharedStats.xp
        level = character.baseStats.level
        toNext = xpPerLevelUp[character.baseStats.level] - xp

        name = character.name
        skillPoints = character.skillPoints

        # Draw values
        #  Name
        printScr(name, self.posx+148, self.posy+16, (255,255,255), self.font, screen)
        #  HP
        printScr(f"HP:{hp:4}/{hpMax:4}", self.posx+148, self.posy+36, (255,255,255), self.font, screen)
        drawHorizontalBar(screen, self.posx+280, self.posy+28, 160, 16, (0,255,0), hp, hpMax)
        #  Level
        printScr(f"Level {level:2}", self.posx+148, self.posy+56, (255,255,255), self.font, screen)
        #  XP to next
        if level < 20:
            drawHorizontalBar(screen, self.posx+280, self.posy+48, 160, 16, (0,255,255), xp, xpPerLevelUp[level])
            printScr(f"To next level: {toNext:8}", self.posx+148, self.posy+76, (255,255,255), self.font, screen)
        else:
            drawHorizontalBar(screen, self.posx+280, self.posy+48, 160, 16, (0,255,255), 1, 1)
            printScr(f"MAX LEVEL", self.posx+148, self.posy+76, (255,255,255), self.font, screen)
        #  Class
        printScr(f"Class: {className:10}", self.posx+148, self.posy+96, (255,255,255), self.font, screen)
        printScr(f"Unspent Skill Points: {skillPoints:2}", self.posx+148, self.posy+116, (255,255,255), self.font, screen)

class SharedStatsMenu(MenuItem):
    def __init__(self, posx, posy, visible):
        self.posx = posx
        self.posy = posy
        self.visible = visible
        self.font = pg.font.SysFont("Courier", 16)
    def draw(self, screen, world):
        sharedStats = xp = world.get_component(dialog.PlayerData)[0][1].sharedStats
        drawMenuBox(screen, self.posx, self.posy, 500, 50)
        printScr(f"TP:{sharedStats.tp:3}/{sharedStats.tpMax:3}  {sharedStats.gold:6} Gold  {0:6} Crystals", self.posx+24, self.posy+24, (255,255,255), self.font, screen)

class OptionsMenu(MenuItem):
    def __init__(self, left, top, length, height, optionList, visible):
        self.left = left
        self.top = top
        self.length = length
        self.height = height
        self.optionList = optionList
        self.visible = visible
        self.font = pg.font.SysFont("Courier", 20)
        self.conditions = [dialog.Condition() for i in range(len(self.optionList))]
    def ConditionMenu(left, top, length, height, optionList, visible, conditionList):
        menu = OptionsMenu(left, top, length, height, optionList, visible)
        menu.conditions = conditionList
        return menu
    def draw(self, screen, world):
        drawMenuBox(screen, self.left, self.top, self.length, self.height)
        if len(world.get_component(dialog.PlayerData)) > 0:
            playerData = world.get_component(dialog.PlayerData)[0][1]
        else:
            playerData = dialog.PlayerData([],[],[],[],battle.SharedStats(0,0,0,0),"none")        
        for i, option in enumerate(self.optionList):
            if self.conditions[i].verify("", playerData):
                printScr(option, self.left+16, self.top+24+i*48, (255,255,255), self.font, screen)
            else:
                printScr(option, self.left+16, self.top+24+i*48, (150,150,150), self.font, screen)

class BackgroundMenu(MenuItem):
    def __init__(self, visible):
        self.visible = visible
    def draw(self, screen, world):
        drawMenuBox(screen, 2, 2, 636, 476)